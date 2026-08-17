import discord
from discord.ext import commands, tasks
import asyncio
import os
import sys
import random
import re
import inspect
from typing import Dict, Any, Callable, Optional, Tuple, Set, List

# Force UTF-8 on Windows Console to avoid charmap / emoji encoding crashes
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# --- OPUS AUDIO LIBRARY LOADER (Required for Discord Voice on Windows) ---
try:
    if not discord.opus.is_loaded():
        possible_opus_paths = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'opus.dll'),
            os.path.abspath('opus.dll'),
            r'C:\Users\Administrator\Videos\App bot\proj\LoudBot\.venv\Lib\site-packages\discord\bin\libopus-0.x64.dll',
            r'C:\Users\Administrator\Documents\Loud\LOUD\LOUD\ok\Lib\site-packages\discord\bin\libopus-0.x64.dll'
        ]
        loaded = False
        for path in possible_opus_paths:
            if os.path.exists(path):
                try:
                    discord.opus.load_opus(path)
                    print(f"[OPUS LOADED]: Loaded voice encoder library from: {path}")
                    loaded = True
                    break
                except Exception:
                    pass
        if not loaded:
            print("[OPUS WARNING]: opus.dll not found. Voice playback might drop if libopus is missing.")
except Exception as e:
    print(f"[OPUS INIT ERROR]: {e}")

# --- CONFIGURATION CONSTANTS ---
try:
    from config import SONGS_FOLDER, DEFAULT_VOLUME, MIN_VOLUME, MAX_VOLUME, VOLUME_STEP
except ImportError:
    SONGS_FOLDER = 'audio'
    DEFAULT_VOLUME = 150
    MIN_VOLUME = 50
    MAX_VOLUME = 200
    VOLUME_STEP = 10

TOKEN_FILE = 'tokens.txt'
WHITELIST_FILE = 'whitelist.txt'
SPAM_MESSAGE = "# XYPHER X ALWAYS ON TOP BABE"
SPAM_DURATION = 30.0  # default seconds
SPAM_WORKERS_PER_BOT = 4  # 4 bots * 4 workers = 16 parallel blaster streams for 100x speed

# Ensure audio directory exists
os.makedirs(SONGS_FOLDER, exist_ok=True)


class LoudBotSystem:
    """
    Manages the Master-Worker multi-bot architecture:
    - Bot 0 is the Master Controller (listens to commands & outputs responses).
    - Bot 1, 2, 3 are Worker Nodes (synchronized audio streamers & chat spammers).
    """
    def __init__(self):
        print("[SYSTEM CORE]: Initializing Bot Manager Core (Master-Worker Architecture)...")
        self.bot_instances: Dict[int, discord.Client] = {}
        self.bot_tokens: Dict[int, str] = {}
        self.whitelisted_users: Set[int] = set()
        self.current_song_path: Optional[str] = None
        self.target_voice_channel_id: Optional[int] = None
        self.is_playing: bool = False
        self.is_spamming: bool = False
        self.spam_task: Optional[asyncio.Task] = None

        # Lock to prevent concurrent voice join operations
        self.voice_join_lock = asyncio.Lock()

        self.global_state: Dict[str, Any] = {
            'looping': True,
            'volume': DEFAULT_VOLUME
        }

        # Initialize whitelist
        self.load_whitelist()

    # ==================================================================
    # WHITELIST MANAGEMENT (Only for Command Authorization)
    # ==================================================================

    def load_whitelist(self):
        """Loads whitelisted Discord user IDs from whitelist.txt."""
        self.whitelisted_users = set()
        if not os.path.exists(WHITELIST_FILE):
            try:
                with open(WHITELIST_FILE, 'w', encoding='utf-8') as f:
                    f.write("# Add whitelisted Discord User IDs below (one ID per line)\n")
                print(f"[WHITELIST]: Created initial {WHITELIST_FILE}")
            except Exception as e:
                print(f"[WHITELIST ERROR]: Could not create {WHITELIST_FILE}: {e}")
            return

        try:
            with open(WHITELIST_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    try:
                        user_id = int(line.split()[0])
                        self.whitelisted_users.add(user_id)
                    except ValueError:
                        continue
        except Exception as e:
            print(f"[WHITELIST ERROR]: Could not read {WHITELIST_FILE}: {e}")

    def is_user_whitelisted(self, user_id: int) -> bool:
        """Checks if a user ID is whitelisted. Reloads file to reflect real-time changes."""
        self.load_whitelist()
        return user_id in self.whitelisted_users

    def add_to_whitelist(self, user_id: int) -> bool:
        """Appends a new user ID to whitelist.txt and updates memory."""
        try:
            self.whitelisted_users.add(user_id)
            with open(WHITELIST_FILE, 'a', encoding='utf-8') as f:
                f.write(f"\n{user_id}")
            print(f"[WHITELIST]: Added user ID {user_id} to whitelist.")
            return True
        except Exception as e:
            print(f"[WHITELIST ERROR]: Could not write to {WHITELIST_FILE}: {e}")
            return False

    # ==================================================================
    # BOT INITIALIZATION & CONNECTION
    # ==================================================================

    def _load_bots(self):
        """Loads bots from KEY=VALUE format in tokens.txt."""
        print("[LOADER]: Attempting to read credentials from tokens.txt...")
        try:
            with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
                token_data = {}
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, value = line.split('=', 1)
                        token_data[key.strip()] = value.strip()

            self.bot_instances = {}
            self.bot_tokens = {}
            print(f"[LOADER]: Credentials parsed successfully ({len(token_data)} token(s) found).")

            index_counter = 0
            for name, token in token_data.items():
                if index_counter >= 100:
                    print("[LOADER]: Hit safety limit of 100 bots. Stopping load.")
                    break

                try:
                    intents = discord.Intents.default()
                    intents.message_content = True
                    intents.voice_states = True
                    intents.guilds = True
                    activity = discord.Game(name="XYPHER X MASTER" if index_counter == 0 else "XYPHER X NODE")
                    client = discord.Client(intents=intents, activity=activity)

                    self.bot_instances[index_counter] = client
                    self.bot_tokens[index_counter] = token
                    role_tag = "MASTER CONTROLLER" if index_counter == 0 else "WORKER NODE"
                    print(f"[LOADER]: Success - Bot {index_counter} ({name}) initialized as [{role_tag}].")
                    index_counter += 1
                except Exception as e:
                    print(f"[ERROR]: Could not initialize bot '{name}'. Error: {e}")

        except FileNotFoundError:
            print(f"\n[FATAL ERROR]: The file '{TOKEN_FILE}' was not found.")
            print("Action Required: Please create this file with 'KEY=VALUE' pairs (e.g. TOKEN_FOR_BOT_0=your_token).")

    async def initialize_all_bots(self):
        """Connects all bot instances concurrently using asyncio.gather."""
        if not self.bot_instances:
            print("\n[SYSTEM CORE]: Cannot run, no bots initialized.")
            return False

        print(f"\n[SYSTEM CORE]: Attempting to connect {len(self.bot_instances)} bots...")
        tasks = []
        for index, client in self.bot_instances.items():
            token = self.bot_tokens.get(index)
            if token:
                tasks.append(client.start(token))
            else:
                print(f"[ERROR]: No token found for Bot {index}")

        if not tasks:
            print("[CRITICAL FAIL]: No valid bot tasks to execute.")
            return False

        try:
            print("\n=====================================================")
            print("[SUCCESS]: ALL BOTS ARE ONLINE AND LISTENING!")
            print("=====================================================\n")
            await asyncio.gather(*tasks)
            return True
        except Exception as e:
            print(f"[CRITICAL FAIL]: One or more bots disconnected: {e}")
            return False

    # ==================================================================
    # PERMANENT SYNCHRONIZED VOICE JOINING (No Flapping)
    # ==================================================================

    def get_author_voice_channel(self, message: discord.Message) -> Tuple[Optional[discord.Guild], Optional[discord.VoiceChannel]]:
        """Finds the voice channel where the message author is currently staying."""
        author_id = message.author.id

        if message.guild and isinstance(message.author, discord.Member):
            if message.author.voice and message.author.voice.channel:
                return message.guild, message.author.voice.channel

        for client in self.bot_instances.values():
            for guild in client.guilds:
                member = guild.get_member(author_id)
                if member and member.voice and member.voice.channel:
                    return guild, member.voice.channel

        return None, None

    def get_active_voice_clients(self) -> List[Tuple[int, discord.Client, discord.VoiceClient]]:
        """Returns all currently connected voice clients across bots."""
        active = []
        for idx, client in self.bot_instances.items():
            for vc in client.voice_clients:
                if vc.is_connected():
                    active.append((idx, client, vc))
        return active

    async def join_voice_channel_all_bots(self, target_channel: discord.VoiceChannel) -> Tuple[int, str]:
        """
        Connects all loaded bots to the target voice channel stably.
        Uses voice mutex to prevent gateway collisions and reconnect loops.
        """
        async with self.voice_join_lock:
            target_guild = target_channel.guild
            self.target_voice_channel_id = target_channel.id
            connected_count = 0

            for idx, client in self.bot_instances.items():
                try:
                    bot_guild = client.get_guild(target_guild.id)
                    if not bot_guild:
                        print(f"[VOICE]: Bot {idx} ({client.user}) is not in guild '{target_guild.name}' (Invite bot to server)")
                        continue

                    ch = bot_guild.get_channel(target_channel.id)
                    if not ch or not isinstance(ch, (discord.VoiceChannel, discord.StageChannel)):
                        print(f"[VOICE]: Bot {idx} cannot access channel '{target_channel.name}'")
                        continue

                    # Check if already connected to voice in this guild
                    vc = bot_guild.voice_client
                    if vc is not None and vc.is_connected():
                        if vc.channel.id == ch.id:
                            # Already stably in target channel - KEEP IT LOCKED!
                            connected_count += 1
                            continue
                        else:
                            await vc.move_to(ch)
                            connected_count += 1
                            continue

                    # Clean up broken connection state if present
                    if vc is not None and not vc.is_connected():
                        try:
                            await vc.disconnect(force=True)
                        except Exception:
                            pass
                        await asyncio.sleep(0.15)

                    # Connect with timeout and small stagger to prevent Discord gateway collisions
                    new_vc = await ch.connect(timeout=20.0, reconnect=True, self_deaf=False)
                    if new_vc and new_vc.is_connected():
                        connected_count += 1
                    await asyncio.sleep(0.35)

                except discord.ClientException:
                    vc = getattr(client.get_guild(target_guild.id), 'voice_client', None)
                    if vc and vc.is_connected():
                        connected_count += 1
                except Exception as e:
                    print(f"[VOICE JOIN ERROR Bot {idx}]: {e}")

            return connected_count, f"{connected_count} bot(s) locked in '{target_channel.name}'."

    # ==================================================================
    # SYNCHRONIZED AUDIO PLAYBACK & MULTI-TRACK ALLOCATION
    # ==================================================================

    def _get_audio_files(self):
        """Returns a naturally sorted list of audio files in SONGS_FOLDER."""
        if not os.path.exists(SONGS_FOLDER):
            return []
        valid_extensions = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac')
        files = [f for f in os.listdir(SONGS_FOLDER) if f.lower().endswith(valid_extensions)]

        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

        return sorted(files, key=natural_sort_key)

    def _find_song(self, query: str = None) -> Optional[str]:
        """Finds a song file by exact number, index, or filename query."""
        audio_files = self._get_audio_files()
        if not audio_files:
            return None

        if not query:
            return audio_files[0]

        query = str(query).strip().lower()

        # If query is a pure number (e.g. '1', '2', '20')
        if query.isdigit():
            num = int(query)
            for f in audio_files:
                if f.lower() == f"{num}.mp3" or f.lower().startswith(f"{num}."):
                    return f
            if 0 <= num < len(audio_files):
                return audio_files[num]
            if 1 <= num <= len(audio_files):
                return audio_files[num - 1]

        # Search substring in filename
        for f in audio_files:
            if query in f.lower():
                return f

        return None

    async def _start_voice_stream(self, client: discord.Client, bot_idx: int, vc: discord.VoiceClient, song_path: str):
        """Plays audio stream on a single voice client with safe infinite loop callback."""
        if not self.is_playing or not vc.is_connected():
            return
        try:
            if vc.is_playing():
                vc.stop()
                await asyncio.sleep(0.05)

            vol_val = self.global_state.get('volume', DEFAULT_VOLUME) / 100.0
            source = discord.FFmpegPCMAudio(
                song_path,
                options="-vn -loglevel error"
            )
            transformed_source = discord.PCMVolumeTransformer(source, volume=vol_val)

            def make_after(b_idx=bot_idx, cl=client, vclient=vc, path=song_path):
                def after_callback(err):
                    if err:
                        print(f"[AUDIO ERROR Bot {b_idx}]: {err}")
                    if self.is_playing and self.global_state.get('looping', True) and vclient.is_connected():
                        # Seamless infinite replay
                        asyncio.run_coroutine_threadsafe(
                            self._start_voice_stream(cl, b_idx, vclient, path),
                            cl.loop
                        )
                return after_callback

            vc.play(transformed_source, after=make_after())
            print(f"[AUDIO PLAYING]: Bot {bot_idx} streaming '{os.path.basename(song_path)}'")
        except Exception as e:
            print(f"[PLAYBACK ERROR Bot {bot_idx}]: {e}")

    async def play_audio_all_bots(self, song_path: str) -> int:
        """Starts simultaneous single audio playback on all connected bots with infinite loop."""
        active_vcs = self.get_active_voice_clients()
        if not active_vcs:
            return 0

        self.is_playing = True
        self.current_song_path = song_path

        # Flush any currently playing audio
        for idx, client, vc in active_vcs:
            if vc.is_playing():
                vc.stop()

        await asyncio.sleep(0.15)

        # Simultaneously start playback on all voice clients
        tasks = []
        for idx, client, vc in active_vcs:
            tasks.append(self._start_voice_stream(client, idx, vc, song_path))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        return len(tasks)

    async def play_distributed_audio_all_bots(self) -> Tuple[int, List[str]]:
        """
        Plays different music on different bots:
        Allocates first 10 music tracks across the first 10 bots, and repeats allocation for all bots.
        """
        active_vcs = self.get_active_voice_clients()
        if not active_vcs:
            return 0, ["No bots are currently connected to a voice channel. Run `!ja <channel_id>` first!"]

        audio_files = self._get_audio_files()
        if not audio_files:
            return 0, ["No audio files found in audio/ folder."]

        self.is_playing = True
        self.global_state['looping'] = True

        # Stop existing streams
        for idx, client, vc in active_vcs:
            if vc.is_playing():
                vc.stop()

        await asyncio.sleep(0.15)

        num_songs_pool = min(10, len(audio_files))
        tasks = []
        allocations = []

        for idx, client, vc in active_vcs:
            # Allocate song: bot 0 -> song 0, bot 1 -> song 1, ..., modulo 10
            song_idx = idx % num_songs_pool
            song_name = audio_files[song_idx]
            song_path = os.path.join(SONGS_FOLDER, song_name)
            allocations.append(f"Bot {idx} -> `{song_name}`")
            tasks.append(self._start_voice_stream(client, idx, vc, song_path))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        return len(tasks), allocations

    async def stop_audio_all_bots(self):
        """Stops audio across all bots without leaving the voice channel."""
        self.is_playing = False
        for client in self.bot_instances.values():
            for vc in client.voice_clients:
                if vc.is_playing():
                    vc.stop()

    async def disconnect_all_bots(self):
        """Stops audio, cancels spam, and disconnects all bots from voice channels."""
        self.is_playing = False
        self.is_spamming = False
        self.target_voice_channel_id = None
        if self.spam_task and not self.spam_task.done():
            self.spam_task.cancel()

        for client in self.bot_instances.values():
            for vc in client.voice_clients:
                try:
                    if vc.is_playing():
                        vc.stop()
                    await vc.disconnect(force=True)
                except Exception as e:
                    print(f"[DISCONNECT ERROR]: {e}")

    # ==================================================================
    # MULTI-BOT 100x ZERO-DELAY ULTRA SPAM STORM (All Bots Participate in Chat)
    # ==================================================================

    def _parse_spam_args(self, args: list) -> Tuple[Optional[int], str]:
        """
        Parses !spam [count] {text}
        Prefixes '# ' to text automatically.
        """
        if not args:
            return None, SPAM_MESSAGE

        count = None
        text_parts = list(args)

        # Check if first token is a count number
        if text_parts[0].isdigit():
            count = int(text_parts.pop(0))

        raw_text = " ".join(text_parts).strip()

        # Strip optional enclosing brackets like {text} or [text]
        if raw_text.startswith('{') and raw_text.endswith('}'):
            raw_text = raw_text[1:-1].strip()
        elif raw_text.startswith('[') and raw_text.endswith(']'):
            raw_text = raw_text[1:-1].strip()

        if not raw_text:
            raw_text = "XYPHER X ALWAYS ON TOP BABE"

        # Ensure '# ' prefix
        if not raw_text.startswith('#'):
            formatted_text = f"# {raw_text}"
        else:
            formatted_text = f"# {raw_text.lstrip('#').strip()}"

        return count, formatted_text

    def start_spam_task(self, channel: discord.abc.Messageable, custom_text: str = SPAM_MESSAGE, count: Optional[int] = None, duration: float = SPAM_DURATION):
        """Spawns an ultra-high-speed 0-delay multi-bot spam storm across all bots."""
        self.is_spamming = True
        if self.spam_task and not self.spam_task.done():
            self.spam_task.cancel()
        self.spam_task = asyncio.create_task(self._spam_worker(channel, custom_text=custom_text, count=count, duration=duration))

    async def _spam_worker(self, channel: discord.abc.Messageable, custom_text: str = SPAM_MESSAGE, count: Optional[int] = None, duration: float = SPAM_DURATION):
        """Fires messages with 0 delay across all bots concurrently."""
        self.is_spamming = True
        desc = f"{count} messages" if count else f"{duration}s"
        print(f"[SPAM]: Unleashing 100x ZERO-DELAY spam storm ({desc}): '{custom_text}'...")

        end_time = asyncio.get_event_loop().time() + duration
        total_sent = 0
        counter_lock = asyncio.Lock()

        async def worker_sender(bot_idx: int, worker_id: int, client: discord.Client):
            nonlocal total_sent
            target_ch = channel
            if hasattr(channel, 'guild') and channel.guild:
                b_guild = client.get_guild(channel.guild.id)
                if b_guild:
                    b_ch = b_guild.get_channel(channel.id)
                    if b_ch:
                        target_ch = b_ch

            # 0-delay firing loop
            while self.is_spamming:
                if count is not None:
                    async with counter_lock:
                        if total_sent >= count:
                            break
                        total_sent += 1
                else:
                    if asyncio.get_event_loop().time() >= end_time:
                        break

                try:
                    await target_ch.send(custom_text)
                except discord.errors.HTTPException as e:
                    if e.status == 429:  # Discord HTTP 429 Rate Limit
                        retry = getattr(e, 'retry_after', 0.2)
                        await asyncio.sleep(retry)
                    else:
                        await asyncio.sleep(0.05)
                except asyncio.CancelledError:
                    break
                except Exception:
                    await asyncio.sleep(0.05)

        # 4 bots * 4 workers = 16 parallel blaster streams
        tasks = []
        for i, client in self.bot_instances.items():
            for w in range(SPAM_WORKERS_PER_BOT):
                tasks.append(asyncio.create_task(worker_sender(i, w, client)))

        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            for t in tasks:
                t.cancel()
        finally:
            self.is_spamming = False
            print(f"[SPAM]: Spam storm ({desc}) completed.")

    # ==================================================================
    # MASTER CONTROLLER ROUTER & HANDLERS (Executed ONLY on Bot 0)
    # ==================================================================

    async def handle_master_commands(self, message: discord.Message):
        """
        Master router executed strictly on Bot 0 (Master Bot).
        Bot 0 controls all other bots and produces all command reply outputs.
        """
        content = message.content.strip()
        if not content.startswith('!'):
            return None

        # Parse command structure
        parts = content[1:].split()
        if not parts:
            return None
        cmd_base = parts[0].lower()
        args = parts[1:]

        # --- 1. WHITELIST MANAGEMENT COMMANDS ---
        if cmd_base == 'u':
            if args:
                try:
                    target_id = int(args[0])
                    if self.add_to_whitelist(target_id):
                        return f"[WHITELIST]: User ID `{target_id}` added to whitelist."
                    else:
                        return f"[ERROR]: Could not add User ID `{target_id}` to whitelist."
                except ValueError:
                    return "[COMMAND ERROR]: Usage: `!u <user_id>` (e.g. `!u 1480822622429253643`)"
            return "[COMMAND ERROR]: Usage: `!u <user_id>`"

        elif cmd_base in ['wl', 'whitelist']:
            self.load_whitelist()
            if not self.whitelisted_users:
                return "[WHITELIST]: Whitelist is currently empty. Add users with `!u <user_id>` or edit `whitelist.txt`."
            wl_list = "\n".join([f"- `{uid}`" for uid in sorted(self.whitelisted_users)])
            return f"**Whitelisted Users ({len(self.whitelisted_users)}):**\n{wl_list}"

        # --- 2. DEDICATED 100x ZERO-DELAY SPAM COMMAND (!spam [count] {text}) ---
        elif cmd_base == 'spam':
            count, text_to_spam = self._parse_spam_args(args)
            self.start_spam_task(message.channel, custom_text=text_to_spam, count=count)
            count_desc = f"{count} messages" if count else f"{SPAM_DURATION} seconds"
            return f"[SPAM]: ⚡ **100x ZERO-DELAY SPAM STORM TRIGGERED ({count_desc})**:\n> {text_to_spam}"

        # --- 3. VOICE JOIN COMMAND (!ja [voice_channel_id]) ---
        elif cmd_base in ['ja', 'join']:
            target_vc = None
            if args:
                try:
                    target_id = int(args[0])
                    for c in self.bot_instances.values():
                        ch = c.get_channel(target_id)
                        if ch and isinstance(ch, (discord.VoiceChannel, discord.StageChannel)):
                            target_vc = ch
                            break
                    if not target_vc:
                        for c in self.bot_instances.values():
                            try:
                                ch = await c.fetch_channel(target_id)
                                if ch and isinstance(ch, (discord.VoiceChannel, discord.StageChannel)):
                                    target_vc = ch
                                    break
                            except Exception:
                                pass
                    if not target_vc:
                        return f"[VOICE ERROR]: Could not find voice channel with ID `{target_id}`."
                except ValueError:
                    pass

            if not target_vc:
                guild, user_vc = self.get_author_voice_channel(message)
                if not user_vc:
                    return "[VOICE ERROR]: Please specify a Channel ID: `!ja <channel_id>` (or join a voice channel)."
                target_vc = user_vc

            joined_count, join_msg = await self.join_voice_channel_all_bots(target_vc)
            return f"[VOICE]: {join_msg} *(Bots will stay locked in channel permanently until `!dc` is triggered)*"

        # --- 4. PLAYBACK COMMANDS (!p, !1, !2, ..., !21) ---
        elif cmd_base == 'p' or cmd_base.isdigit():
            # Check if bots are currently in a voice channel
            active_vcs = self.get_active_voice_clients()
            if not active_vcs:
                return "[VOICE ERROR]: Bots are not locked in a voice channel! Run `!ja <channel_id>` to join first."

            # Check if user ran "!p" (no track specified) -> DISTRIBUTED ALLOCATION
            if cmd_base == 'p' and not args:
                count_playing, alloc_list = await self.play_distributed_audio_all_bots()
                if count_playing == 0:
                    return f"[VOICE ERROR]: {alloc_list[0]}"
                alloc_summary = "\n".join([f"- {a}" for a in alloc_list])
                return (
                    f"🎶 **[DISTRIBUTED PLAYBACK]**: {count_playing} bots playing unique tracks with **INFINITE LOOP**!\n"
                    f"{alloc_summary}\n*(Allocation repeats across all bots)*"
                )

            # Specific track requested (e.g. !p 3, !1, !2, etc.)
            if cmd_base.isdigit():
                query = cmd_base
            else:
                query = " ".join(args)

            chosen_song = self._find_song(query)
            if not chosen_song:
                audio_files = self._get_audio_files()
                return (
                    f"[AUDIO ERROR]: Could not find song `{query}`.\n"
                    f"Available ({len(audio_files)}): {', '.join(audio_files[:10])}..."
                )

            song_path = os.path.join(SONGS_FOLDER, chosen_song)
            self.global_state['looping'] = True
            played_count = await self.play_audio_all_bots(song_path)

            return f"[PLAYING]: **{chosen_song}** simultaneously on {played_count} bot(s) with **INFINITE LOOP**!"

        # --- 5. STOP & DISCONNECT COMMANDS ---
        elif cmd_base in ['s', 'stop']:
            await self.stop_audio_all_bots()
            return "[STOP]: Audio playback stopped across all bots. *(Bots remain permanently in voice channel)*"

        elif cmd_base in ['dc', 'leave', 'disconnect']:
            await self.disconnect_all_bots()
            return "[DISCONNECT]: All bots disconnected from voice channels."

        elif cmd_base in ['l', 'loop']:
            self.global_state['looping'] = not self.global_state.get('looping', True)
            state = "ENABLED (Infinite)" if self.global_state['looping'] else "DISABLED"
            return f"[STATE UPDATE]: Audio Looping is now **{state}**."

        # --- 6. VOLUME COMMANDS ---
        elif cmd_base == 'vol':
            if args:
                try:
                    vol = int(args[0])
                    return await self.command_set_volume(vol)
                except ValueError:
                    return "[COMMAND ERROR]: Usage: `!vol <50-200>` (e.g. `!vol 150`)"
            return f"[STATE]: Current global volume is **{self.global_state['volume']}%**."

        elif cmd_base == 'volup':
            return await self.command_volume_up()

        elif cmd_base == 'voldown':
            return await self.command_volume_down()

        # --- 7. SONG LIST & STATUS COMMANDS ---
        elif cmd_base == 'songs':
            return await self._list_available_songs()

        elif cmd_base in ['status', 'check', 'load']:
            return await self._run_status_check()

        else:
            return f"[CMD FAIL]: Unknown command `!{cmd_base}`. Available: `!p` *(distributed)*, `!1`-`!21`, `!ja <channel_id>`, `!spam [count] {text}`, `!s`, `!dc`, `!vol <num>`, `!loop`, `!songs`, `!u <id>`, `!wl`, `!status`."

    # ==================================================================
    # HELPER ACTIONS & STATE CONTROLS
    # ==================================================================

    async def _run_status_check(self):
        """Worker for !status / !check."""
        connected_voice = len(self.get_active_voice_clients())
        master_name = str(self.bot_instances.get(0, {}).user) if 0 in self.bot_instances else "Bot 0"
        return (
            f"**=== System Status ===**\n"
            f"- **Master Controller**: {master_name} (Bot 0)\n"
            f"- **Worker Nodes**: {len(self.bot_instances) - 1}\n"
            f"- **Voice Connected**: {connected_voice} bot(s)\n"
            f"- **Target VC ID**: {self.target_voice_channel_id or 'None'}\n"
            f"- **Currently Playing**: {os.path.basename(self.current_song_path) if (self.is_playing and self.current_song_path) else 'None'}\n"
            f"- **Spamming**: {'ACTIVE' if self.is_spamming else 'OFF'}\n"
            f"- **Global Volume**: {self.global_state['volume']}%\n"
            f"- **Looping**: {'ON (Infinite)' if self.global_state['looping'] else 'OFF'}\n"
            f"- **Whitelisted Users**: {len(self.whitelisted_users)}"
        )

    async def command_set_volume(self, volume: int):
        """Updates shared volume and applies to active voice clients."""
        clamped_vol = max(MIN_VOLUME, min(MAX_VOLUME, volume))
        self.global_state['volume'] = clamped_vol

        # Update live streams
        for client in self.bot_instances.values():
            for vc in client.voice_clients:
                if vc.source and isinstance(vc.source, discord.PCMVolumeTransformer):
                    vc.source.volume = clamped_vol / 100.0

        return f"[STATE SYNC]: Global volume set to **{clamped_vol}%**."

    async def command_volume_up(self):
        """Increases shared volume."""
        return await self.command_set_volume(self.global_state['volume'] + VOLUME_STEP)

    async def command_volume_down(self):
        """Decreases shared volume."""
        return await self.command_set_volume(self.global_state['volume'] - VOLUME_STEP)

    async def _list_available_songs(self):
        """Handles !songs by listing files in SONGS_FOLDER."""
        files = self._get_audio_files()
        if not files:
            return f"[SONGS]: No audio files found in `{SONGS_FOLDER}/`. Add `.mp3`, `.wav`, or `.ogg` files into the audio folder."

        output = f"**=== Available Songs ({len(files)}) ===**\n"
        for idx, song in enumerate(files):
            output += f"`[{idx + 1}]`: {song}\n"
        output += "\nRun `!p` to distribute different songs across all bots, or `!p <number>` to play a single song simultaneously!"
        return output


# ==================================================================
# MAIN ENTRYPOINT
# ==================================================================

async def main():
    manager = LoudBotSystem()

    # 1. Load tokens and clients
    manager._load_bots()

    if not manager.bot_instances:
        print("\n[FINAL]: Execution halted because no bots could be loaded.")
        return

    # Print whitelist status
    if not manager.whitelisted_users:
        print("\n[WHITELIST NOTICE]: whitelist.txt is currently empty!")
        print(">>> Add your Discord User ID to whitelist.txt or you will not be able to issue commands.\n")
    else:
        print(f"[WHITELIST]: Active whitelist IDs: {list(manager.whitelisted_users)}")

    # --- ATTACHING LISTENERS: MASTER BOT (Bot 0) ONLY ---
    print("\n[LOGGER]: Configuring Master-Worker Event Handlers...")
    for i, client in manager.bot_instances.items():
        # ONLY Bot 0 (Master) gets on_message handler to listen and respond to commands
        if i == 0:
            @client.event
            async def on_message(message: discord.Message):
                # Ignore bots
                if message.author.bot:
                    return

                content = message.content.strip()
                if not content.startswith('!'):
                    return

                # Whitelist authorization check
                if not manager.is_user_whitelisted(message.author.id):
                    return

                # Execute on Master Bot 0
                response = await manager.handle_master_commands(message)
                if response:
                    try:
                        await message.channel.send(response)
                    except Exception as e:
                        print(f"[ERROR Master Bot 0]: Could not send response message: {e}")

            print("[LISTENER]: [MASTER CONTROLLER] Command Listener attached to Bot 0 (CELPHYX).")

        # All bots get on_ready for connection logging
        def make_ready_handler(bot_idx, bot_client):
            async def on_ready():
                role = "MASTER CONTROLLER" if bot_idx == 0 else "WORKER NODE"
                print(f"[ONLINE]: Bot {bot_idx} connected as {bot_client.user} (ID: {bot_client.user.id if bot_client.user else 'N/A'}) [{role}]")
            return on_ready

        client.event(make_ready_handler(i, client))

    print("\n=====================================================")
    print("STARTING BOTS AND CONNECTING TO DISCORD GATEWAY...")
    print("INTERACTION GUIDANCE: Message Master Bot 0 in Discord to run commands.")
    print("STOPPING GRACEFULLY: Press CTRL+C in this console.")
    print("=====================================================")

    # 2. Connect all clients
    await manager.initialize_all_bots()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[SYSTEM SHUTDOWN]: Ctrl+C detected. Initiating graceful shutdown.")
        print("Manager finished execution cycle.")