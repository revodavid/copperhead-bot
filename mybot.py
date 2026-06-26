#!/usr/bin/env python3
"""
CopperHead Bot Template - Your custom Snake game AI.

This bot connects to a CopperHead server and plays Snake autonomously.
Modify the calculate_move() function to implement your own strategy!

QUICK START
-----------
1. Install dependencies:   pip install -r requirements.txt
2. Run:                     python mybot.py --server ws://localhost:8765/ws/

For Codespaces, use the wss:// URL shown in the terminal, e.g.:
    python mybot.py --server wss://your-codespace-url.app.github.dev/ws/

WHAT TO CHANGE
--------------
The calculate_move() function (around line 200) is where your bot decides
which direction to move. The default strategy is simple: chase the nearest
food while avoiding walls and snakes. You can make it smarter!

Ideas for improvement:
  - Avoid getting trapped in dead ends (flood fill)
  - Predict where the opponent will move
  - Use different strategies based on snake length
  - Block the opponent from reaching food
"""

import asyncio
import json
import argparse
import random
import websockets


# ============================================================================
#  BOT CONFIGURATION - Change these to customize your bot
# ============================================================================

# The CopperHead server to connect to. Set this to your server's URL so you
# don't need to pass --server every time. Use "ws://" for local servers or
# "wss://" for Codespaces/remote servers.
GAME_SERVER = "ws://localhost:8765/ws/"

# Your bot's display name (shown to all players in the tournament)
BOT_NAME = "MyBot"

# How your bot appears in logs
BOT_VERSION = "1.0"


# --- Strategy tuning weights (higher = stronger pull) ---
W_FOOD_CAPTURE = 1000   # landing exactly on food
W_FOOD_PROX    = 8      # per-cell closer to nearest food
W_SPACE        = 14     # per reachable cell (flood fill) — dominant safety term
W_EDGE         = 3      # mild center bias
W_TRAP_PENALTY = 100000 # move whose reachable area < our length (near-certain death)
W_HEAD_LOSE    = 6000   # entering a cell the opponent can also enter & we lose/tie
W_HEAD_WIN     = 700    # winnable head-to-head (we're longer) — offensive bonus


# ============================================================================
#  BOT CLASS - Handles connection and game logic
# ============================================================================

class MyBot:
    """A CopperHead bot that connects to the server and plays Snake."""

    def __init__(self, server_url: str, name: str = None):
        self.server_url = server_url
        self.name = name or BOT_NAME
        self.player_id = None
        self.game_state = None
        self.running = False
        self.room_id = None
        # Grid dimensions (updated automatically from server)
        self.grid_width = 30
        self.grid_height = 20

    def log(self, msg: str):
        """Print a message to the console."""
        print(msg.encode("ascii", errors="replace").decode("ascii"))

    # ========================================================================
    #  CONNECTION - You probably don't need to change anything below here
    #  until you get to calculate_move()
    # ========================================================================

    async def wait_for_open_competition(self):
        """Wait until the server is reachable, then return.
        
        Bots always join the lobby regardless of competition state —
        the lobby is always available and the bot will wait there until
        the next competition starts.
        """
        import aiohttp

        base_url = self.server_url.rstrip("/")
        if base_url.endswith("/ws"):
            base_url = base_url[:-3]
        # Convert ws:// to http:// for the REST API
        http_url = base_url.replace("ws://", "http://").replace("wss://", "https://")

        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{http_url}/status") as resp:
                        if resp.status == 200:
                            self.log("Server reachable - joining lobby...")
                            return True
                        else:
                            self.log(f"Server not ready (status {resp.status}), waiting...")
            except Exception as e:
                self.log(f"Cannot reach server: {e}, retrying...")

            await asyncio.sleep(5)

    async def connect(self):
        """Connect to the game server."""
        await self.wait_for_open_competition()

        base_url = self.server_url.rstrip("/")
        if base_url.endswith("/ws"):
            base_url = base_url[:-3]
        url = f"{base_url}/ws/join"

        try:
            self.log(f"Connecting to {url}...")
            self.ws = await websockets.connect(url)
            self.log("Connected! Joining lobby...")
            # Send join message to enter the lobby
            await self.ws.send(json.dumps({
                "action": "join",
                "name": self.name
            }))
            return True
        except Exception as e:
            self.log(f"Connection failed: {e}")
            return False

    async def play(self):
        """Main game loop. Runs until disconnected or eliminated."""
        if not await self.connect():
            self.log("Failed to connect. Exiting.")
            return

        self.running = True

        try:
            while self.running:
                message = await self.ws.recv()
                data = json.loads(message)
                await self.handle_message(data)
        except websockets.ConnectionClosed:
            self.log("Disconnected from server.")
        except Exception as e:
            self.log(f"Error: {e}")
        finally:
            self.running = False
            try:
                await self.ws.close()
            except Exception:
                pass
            self.log("Bot stopped.")

    async def handle_message(self, data: dict):
        """Process messages from the server and respond appropriately."""
        msg_type = data.get("type")

        if msg_type == "error":
            self.log(f"Server error: {data.get('message', 'Unknown error')}")
            self.running = False

        elif msg_type == "joined":
            # Server assigned us a player ID and room
            self.player_id = data.get("player_id")
            self.room_id = data.get("room_id")
            self.log(f"Joined Arena {self.room_id} as Player {self.player_id}")

            # Tell the server we're ready to play
            await self.ws.send(json.dumps({
                "action": "ready",
                "mode": "two_player",
                "name": self.name
            }))
            self.log(f"Ready! Playing as '{self.name}'")

        elif msg_type == "state":
            # Game state update - this is where we decide our next move
            self.game_state = data.get("game")
            grid = self.game_state.get("grid", {})
            if grid:
                self.grid_width = grid.get("width", self.grid_width)
                self.grid_height = grid.get("height", self.grid_height)

            if self.game_state and self.game_state.get("running"):
                direction = self.calculate_move()
                if direction:
                    await self.ws.send(json.dumps({
                        "action": "move",
                        "direction": direction
                    }))

        elif msg_type == "start":
            self.log("Game started!")

        elif msg_type == "gameover":
            winner = data.get("winner")
            my_wins = data.get("wins", {}).get(str(self.player_id), 0)
            opp_id = 3 - self.player_id
            opp_wins = data.get("wins", {}).get(str(opp_id), 0)
            points_to_win = data.get("points_to_win", 5)

            if winner == self.player_id:
                self.log(f"Won! (Score: {my_wins}-{opp_wins}, first to {points_to_win})")
            elif winner:
                self.log(f"Lost! (Score: {my_wins}-{opp_wins}, first to {points_to_win})")
            else:
                self.log(f"Draw! (Score: {my_wins}-{opp_wins}, first to {points_to_win})")

            # Signal ready for next game in the match
            await self.ws.send(json.dumps({
                "action": "ready",
                "name": self.name
            }))

        elif msg_type == "match_complete":
            winner_id = data.get("winner", {}).get("player_id")
            winner_name = data.get("winner", {}).get("name", "Unknown")
            final_score = data.get("final_score", {})
            my_score = final_score.get(str(self.player_id), 0)
            opp_id = 3 - self.player_id
            opp_score = final_score.get(str(opp_id), 0)

            if winner_id == self.player_id:
                self.log(f"Match won! Final: {my_score}-{opp_score}")
                self.log("Waiting for next round...")
            else:
                self.log(f"Match lost to {winner_name}. Final: {my_score}-{opp_score}")
                self.log("Eliminated. Exiting.")
                self.running = False

        elif msg_type == "match_assigned":
            # Assigned to a new match in the next tournament round
            self.room_id = data.get("room_id")
            self.player_id = data.get("player_id")
            self.game_state = None
            opponent = data.get("opponent", "Opponent")
            self.log(f"Next round! Arena {self.room_id} vs {opponent}")
            # Signal ready to the server
            await self.ws.send(json.dumps({"action": "ready", "name": self.name}))

        elif msg_type in ("lobby_joined", "lobby_update"):
            # In the lobby waiting for the competition to start
            if msg_type == "lobby_joined":
                self.log(f"Joined lobby as '{data.get('name', self.name)}'")

        elif msg_type in ("lobby_left", "lobby_kicked"):
            self.log("Removed from lobby.")
            self.running = False

        elif msg_type == "competition_complete":
            champion = data.get("champion", {}).get("name", "Unknown")
            self.log(f"Tournament complete! Champion: {champion}")
            self.running = False

        elif msg_type == "waiting":
            self.log("Waiting for opponent...")

    # ========================================================================
    #  YOUR AI STRATEGY - Modify calculate_move() to change how your bot plays
    # ========================================================================

    def calculate_move(self) -> str | None:
        """Decide which direction to move (Balanced, buff-aware strategy).

        Called every game tick with the current game state; returns one of
        "up", "down", "left", "right" (or None when there's nothing to do).

        Strategy overview:
            1. Build the set of solid cells (snake bodies), correctly keeping a
               tail solid when that snake is about to eat and grow.
            2. Model where the opponent's head can move next tick.
            3. Score each non-reversing, in-bounds, non-body move by:
                 - flood-fill reachable space (dominant anti-trap signal),
                 - food capture / proximity,
                 - head-to-head contention (win if longer, else avoid),
                 - mild center bias.
            4. React to active buffs (shield/ghost/scissors/speed).

        Available data:
            self.game_state     - Full game state (see README for format)
            self.player_id      - Your player number (1 or 2)
            self.grid_width     - Width of the game board
            self.grid_height    - Height of the game board
        """
        if not self.game_state:
            return None

        snakes = self.game_state.get("snakes", {})
        my_snake = snakes.get(str(self.player_id))
        if not my_snake or not my_snake.get("body"):
            return None

        head = my_snake["body"][0]
        current_dir = my_snake.get("direction", "right")
        my_len = len(my_snake["body"])
        my_buff = my_snake.get("buff", "default")

        W, H = self.grid_width, self.grid_height
        foods = self.game_state.get("foods", [])
        food_cells = {(f["x"], f["y"]) for f in foods}

        directions = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
        opposites = {"up": "down", "down": "up", "left": "right", "right": "left"}

        # --- Build danger set. Tail vacates next tick UNLESS that snake is about
        #     to eat (head adjacent to food) and therefore grows. ---
        # If we have shield/ghost we can pass through bodies, so skip them.
        pass_through_bodies = my_buff in ("shield", "ghost")
        dangerous = set()
        if not pass_through_bodies:
            for snake_data in snakes.values():
                body = snake_data.get("body", [])
                if not body:
                    continue
                s_head = body[0]
                growing = any(abs(s_head[0] - f["x"]) + abs(s_head[1] - f["y"]) == 1
                              for f in foods)
                segments = body if growing else body[:-1]
                for seg in segments:
                    dangerous.add((seg[0], seg[1]))

        # --- Opponent next-head reachable cells (for head-to-head reasoning) ---
        opp_next = set()
        opp_len = 0
        opp_buff = "default"
        for pid, snake_data in snakes.items():
            if pid == str(self.player_id) or not snake_data.get("body"):
                continue
            opp_len = len(snake_data["body"])
            opp_buff = snake_data.get("buff", "default")
            o_head = snake_data["body"][0]
            o_dir = snake_data.get("direction", "right")
            for d, (dx, dy) in directions.items():
                if d == opposites.get(o_dir):
                    continue
                opp_next.add((o_head[0] + dx, o_head[1] + dy))

        def in_bounds(x, y):
            return 0 <= x < W and 0 <= y < H

        def is_safe(x, y):
            return in_bounds(x, y) and (x, y) not in dangerous

        def reachable_area(sx, sy, limit):
            """Capped BFS flood fill: how many free cells we can reach from (sx, sy)."""
            from collections import deque
            seen = {(sx, sy)}
            q = deque([(sx, sy)])
            area = 0
            while q and area < limit:
                x, y = q.popleft()
                area += 1
                for dx, dy in directions.values():
                    nx, ny = x + dx, y + dy
                    if is_safe(nx, ny) and (nx, ny) not in seen:
                        seen.add((nx, ny))
                        q.append((nx, ny))
            return area

        # Nearest food (Manhattan)
        nearest_food, nearest_dist = None, float("inf")
        for f in foods:
            d = abs(head[0] - f["x"]) + abs(head[1] - f["y"])
            if d < nearest_dist:
                nearest_dist, nearest_food = d, f

        # Candidate moves: non-reversing, in-bounds, not into a solid body
        candidates = []
        for d, (dx, dy) in directions.items():
            if d == opposites.get(current_dir):
                continue
            nx, ny = head[0] + dx, head[1] + dy
            if is_safe(nx, ny):
                candidates.append((d, nx, ny))

        if not candidates:
            # No safe move — keep going / any non-reverse (let the server decide)
            for d in directions:
                if d != opposites.get(current_dir):
                    return d
            return current_dir

        # --- Score each candidate ---
        best_dir, best_score = None, float("-inf")
        space_cap = max(my_len + 2, 12)  # enough to distinguish trap vs. open

        for d, nx, ny in candidates:
            score = 0

            # Space / anti-trap (dominant safety signal)
            area = reachable_area(nx, ny, space_cap)
            score += area * W_SPACE
            if area < my_len:
                score -= W_TRAP_PENALTY

            # Food
            if (nx, ny) in food_cells:
                score += W_FOOD_CAPTURE
            if nearest_food:
                fd = abs(nx - nearest_food["x"]) + abs(ny - nearest_food["y"])
                score += (W + H - fd) * W_FOOD_PROX

            # Head-to-head contention with the opponent
            if (nx, ny) in opp_next:
                we_win = my_len > opp_len and opp_buff not in ("shield", "scissors")
                if my_buff == "scissors" or pass_through_bodies or we_win:
                    score += W_HEAD_WIN          # winnable / cut them down (aggression)
                else:
                    score -= W_HEAD_LOSE         # we'd lose or tie — avoid

            # Mild center bias
            score += min(nx, W - 1 - nx, ny, H - 1 - ny) * W_EDGE

            # Under speed we have half the reaction time → value space more
            if my_buff == "speed":
                score += area * W_SPACE

            if score > best_score:
                best_score, best_dir = score, d

        return best_dir


# ============================================================================
#  MAIN - Parse command line arguments and start the bot
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(description="CopperHead Bot")
    parser.add_argument("--server", "-s", default=GAME_SERVER,
                        help=f"Server WebSocket URL (default: {GAME_SERVER})")
    parser.add_argument("--name", "-n", default=None,
                        help=f"Bot display name (default: {BOT_NAME})")
    parser.add_argument("--difficulty", "-d", type=int, default=5,
                        help="AI difficulty level 1-10 (accepted for compatibility, not yet used)")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress console output")
    args = parser.parse_args()

    bot = MyBot(args.server, name=args.name)

    print(f"{bot.name} v{BOT_VERSION}")
    print(f"  Server: {args.server}")
    print()

    await bot.play()


if __name__ == "__main__":
    asyncio.run(main())
