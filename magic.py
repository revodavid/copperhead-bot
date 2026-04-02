#!/usr/bin/env python3
"""
Advanced CopperHead Bot - Magic Strategy (AGGRESSIVE MODE)

This is an ULTRA-AGGRESSIVE bot with advanced tactics:
  - AGGRESSIVE food pursuit (5000 pts for direct hits!)
  - Grapes prioritized (150 value - highest priority!)
  - Hunts opponents when longer (+2 length advantage)
  - Head-on collision attacks when advantageous
  - Advanced escape protocols when shorter
  - Tail chasing for survival when no food
  - Food blocking strategies
  - Enhanced flood fill for dead end avoidance

Run: python magic.py --server ws://localhost:8765/ws/
"""

import asyncio
import json
import argparse
import random
import websockets
from collections import deque


# ============================================================================
#  BOT CONFIGURATION
# ============================================================================

GAME_SERVER = "ws://localhost:8765/ws/"
BOT_NAME = "MagicBot"
BOT_VERSION = "2.0"

# Food values - how much we want each fruit type (AGGRESSIVE PRIORITIES)
FOOD_VALUES = {
    "apple": 80,      # Was 100, slightly reduced
    "grapes": 150,    # Was 120, now 150 - BIG priority boost!
    "watermelon": 130, # Was 110, now 130
    "strawberry": 110, # Was 105, now 110
    "peach": 110,     # Was 105, now 110
    "cherry": 110,    # Was 105, now 110
    "banana": 90,     # Was 100, now 90
    "orange": 85,     # Was 95, now 85
    "lemon": 80,      # Was 90, now 80
    "kiwi": 80,       # Was 90, now 80
}


# ============================================================================
#  ADVANCED BOT CLASS
# ============================================================================

class MagicBot:
    """Advanced CopperHead bot with sophisticated AI strategy."""

    def __init__(self, server_url: str, name: str = None):
        self.server_url = server_url
        self.name = name or BOT_NAME
        self.player_id = None
        self.game_state = None
        self.running = False
        self.room_id = None
        self.grid_width = 30
        self.grid_height = 20

    def log(self, msg: str):
        """Print a message to the console."""
        print(msg.encode("ascii", errors="replace").decode("ascii"))

    # ========================================================================
    #  CONNECTION HANDLING
    # ========================================================================

    async def wait_for_open_competition(self):
        """Wait until the server is reachable."""
        import aiohttp

        base_url = self.server_url.rstrip("/")
        if base_url.endswith("/ws"):
            base_url = base_url[:-3]
        http_url = base_url.replace("ws://", "http://").replace("wss://", "https://")

        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{http_url}/status") as resp:
                        if resp.status == 200:
                            self.log("Server reachable - joining lobby...")
                            return True
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
            await self.ws.send(json.dumps({
                "action": "join",
                "name": self.name
            }))
            return True
        except Exception as e:
            self.log(f"Connection failed: {e}")
            return False

    async def play(self):
        """Main game loop."""
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
        """Process server messages."""
        msg_type = data.get("type")

        if msg_type == "error":
            self.log(f"Server error: {data.get('message', 'Unknown error')}")
            self.running = False

        elif msg_type == "joined":
            self.player_id = data.get("player_id")
            self.room_id = data.get("room_id")
            self.log(f"✓ Joined Arena {self.room_id} as Player {self.player_id}")
            await self.ws.send(json.dumps({
                "action": "ready",
                "mode": "two_player",
                "name": self.name
            }))
            self.log(f"🎮 Ready! Playing as '{self.name}'")

        elif msg_type == "state":
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
            self.log("🟢 Game started!")

        elif msg_type == "gameover":
            winner = data.get("winner")
            my_wins = data.get("wins", {}).get(str(self.player_id), 0)
            opp_id = 3 - self.player_id
            opp_wins = data.get("wins", {}).get(str(opp_id), 0)
            points_to_win = data.get("points_to_win", 5)

            if winner == self.player_id:
                self.log(f"✅ Won! (Score: {my_wins}-{opp_wins})")
            elif winner:
                self.log(f"❌ Lost! (Score: {my_wins}-{opp_wins})")
            else:
                self.log(f"🟡 Draw! (Score: {my_wins}-{opp_wins})")

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
                self.log(f"🏆 Match won! Final: {my_score}-{opp_score}")
                self.log("🔄 Waiting for next round...")
            else:
                self.log(f"💔 Match lost to {winner_name}. Final: {my_score}-{opp_score}")
                self.log("Eliminated. Exiting.")
                self.running = False

        elif msg_type == "match_assigned":
            self.room_id = data.get("room_id")
            self.player_id = data.get("player_id")
            self.game_state = None
            opponent = data.get("opponent", "Opponent")
            self.log(f"🎯 Next round! Arena {self.room_id} vs {opponent}")
            await self.ws.send(json.dumps({"action": "ready", "name": self.name}))

        elif msg_type in ("lobby_joined", "lobby_update"):
            if msg_type == "lobby_joined":
                self.log(f"📍 Joined lobby as '{data.get('name', self.name)}'")

        elif msg_type in ("lobby_left", "lobby_kicked"):
            self.log("Removed from lobby.")
            self.running = False

        elif msg_type == "competition_complete":
            champion = data.get("champion", {}).get("name", "Unknown")
            self.log(f"🏅 Tournament complete! Champion: {champion}")
            self.running = False

        elif msg_type == "waiting":
            self.log("⏳ Waiting for opponent...")

    # ========================================================================
    #  ADVANCED AI ALGORITHMS
    # ========================================================================

    def flood_fill(self, start_x, start_y, dangerous):
        """Count reachable squares from a position using BFS (flood fill).
        
        This helps us avoid moving into dead ends or tight spaces.
        Returns the count of reachable squares.
        """
        if (start_x, start_y) in dangerous:
            return 0

        visited = set()
        queue = deque([(start_x, start_y)])
        visited.add((start_x, start_y))
        count = 0

        while queue:
            x, y = queue.popleft()
            count += 1

            # Check all 4 adjacent squares
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if (nx, ny) not in visited and (nx, ny) not in dangerous:
                    if 0 <= nx < self.grid_width and 0 <= ny < self.grid_height:
                        visited.add((nx, ny))
                        queue.append((nx, ny))

        return count

    def predict_opponent_position(self, opponent_snake, steps=2):
        """Predict where the opponent will be in N steps.
        
        Simple prediction: assume opponent continues in current direction.
        Returns the predicted head position.
        """
        if not opponent_snake or not opponent_snake.get("body"):
            return None

        head = opponent_snake["body"][0]
        direction = opponent_snake.get("direction", "right")
        
        deltas = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
        dx, dy = deltas.get(direction, (0, 0))
        
        pred_x = head[0] + dx * steps
        pred_y = head[1] + dy * steps
        
        return (pred_x, pred_y)

    def get_opponent_threat_level(self, my_head, opponent_snake, my_length):
        """Evaluate how dangerous the opponent is.
        
        Returns a threat level (0-100):
          0: No threat
          50: Moderate threat (similar length)
          100: Extreme threat (opponent is much longer)
        """
        if not opponent_snake or not opponent_snake.get("body"):
            return 0

        opp_length = len(opponent_snake.get("body", []))
        opp_head = opponent_snake["body"][0]
        
        # Distance to opponent
        dist = abs(my_head[0] - opp_head[0]) + abs(my_head[1] - opp_head[1])
        
        # If opponent is far away, low threat
        if dist > 10:
            return 0
        
        # Calculate threat based on length differential
        length_diff = opp_length - my_length
        
        if length_diff <= -5:
            threat = 10  # We're much longer, low threat
        elif length_diff <= -2:
            threat = 20  # We're longer, low threat
        elif length_diff <= 0:
            threat = 40  # Equal or we're slightly longer
        elif length_diff <= 2:
            threat = 60  # Opponent is slightly longer
        elif length_diff <= 5:
            threat = 80  # Opponent is longer
        else:
            threat = 100  # Opponent is much longer
        
        # Scale threat by proximity (closer = more threatening)
        proximity_mult = max(0.5, 1 - (dist / 15))
        threat = int(threat * proximity_mult)
        
        return min(100, threat)

    def get_food_priority(self, food):
        """Get score for eating a particular food.
        
        Higher-value foods get higher priority.
        """
        return FOOD_VALUES.get(food.get("type", "apple"), 50)

    # ========================================================================
    #  MAIN AI DECISION MAKING
    # ========================================================================

    def calculate_move(self) -> str | None:
        """Advanced move calculation with multiple strategies."""
        if not self.game_state:
            return None

        snakes = self.game_state.get("snakes", {})
        my_snake = snakes.get(str(self.player_id))

        if not my_snake or not my_snake.get("body"):
            return None

        head = my_snake["body"][0]
        current_dir = my_snake.get("direction", "right")
        my_length = len(my_snake.get("body", []))

        # Get opponent info
        opp_id = 3 - self.player_id
        opponent_snake = snakes.get(str(opp_id))
        opp_length = len(opponent_snake.get("body", [])) if opponent_snake else 0

        # Get food and grid info
        foods = self.game_state.get("foods", [])

        # Build dangerous set (all snake bodies except tail)
        dangerous = set()
        for snake_data in snakes.values():
            body = snake_data.get("body", [])
            for segment in body[:-1]:  # Skip tail
                dangerous.add((segment[0], segment[1]))

        # Direction utilities
        directions = {
            "up": (0, -1),
            "down": (0, 1),
            "left": (-1, 0),
            "right": (1, 0)
        }
        opposites = {"up": "down", "down": "up", "left": "right", "right": "left"}

        def is_safe(x, y):
            """Check if position is safe."""
            if x < 0 or x >= self.grid_width or y < 0 or y >= self.grid_height:
                return False
            return (x, y) not in dangerous

        # Find all safe moves
        safe_moves = []
        for direction, (dx, dy) in directions.items():
            if direction == opposites.get(current_dir):
                continue
            new_x, new_y = head[0] + dx, head[1] + dy
            if is_safe(new_x, new_y):
                safe_moves.append({
                    "direction": direction,
                    "x": new_x,
                    "y": new_y
                })

        # No safe moves - emergency fallback
        if not safe_moves:
            for direction in directions:
                if direction != opposites.get(current_dir):
                    return direction
            return current_dir

        # ====================================================================
        #  SCORING SYSTEM - Multiple factors influence move quality
        # ====================================================================

        threat_level = self.get_opponent_threat_level(head, opponent_snake, my_length)
        best_dir = None
        best_score = float('-inf')

        for move in safe_moves:
            score = 0.0
            new_x, new_y = move["x"], move["y"]
            direction = move["direction"]

            # === Factor 1: Food targeting (AGGRESSIVE) ===
            # Find nearest and highest-value food
            best_food = None
            best_food_dist = float('inf')
            best_food_value = 0

            for food in foods:
                food_dist = abs(new_x - food["x"]) + abs(new_y - food["y"])
                food_value = self.get_food_priority(food)

                # More aggressive: prioritize value over distance
                combined_score = food_value * 2 - food_dist

                if combined_score > best_food_value:
                    best_food_value = combined_score
                    best_food = food
                    best_food_dist = food_dist

            if best_food:
                if new_x == best_food["x"] and new_y == best_food["y"]:
                    # DIRECT HIT - MAXIMUM PRIORITY!
                    score += 5000  # Was 2000, now 5000
                else:
                    # Getting closer to food - heavily weighted
                    food_bonus = self.get_food_priority(best_food)
                    dist_to_food = abs(new_x - best_food["x"]) + abs(new_y - best_food["y"])
                    # Much more aggressive food pursuit
                    score += (100 - min(dist_to_food, 100)) * (food_bonus / 50)  # Was 50, now 100

            # === Factor 2: Flood fill (escape routes) ===
            reachable = self.flood_fill(new_x, new_y, dangerous)
            if reachable < 8:
                # Moving into a dead end - penalize heavily
                score -= 500
            else:
                # Bonus for moves with many escape routes
                score += (reachable / 10) * 20

            # === Factor 3: Strategy based on length (ULTRA AGGRESSIVE) ===
            if my_length > opp_length + 2:  # Was +3, now +2 - more aggressive
                # We're longer - HUNT THE OPPONENT!
                opp_head = opponent_snake["body"][0] if opponent_snake else None
                if opp_head:
                    dist_to_opp = abs(new_x - opp_head[0]) + abs(new_y - opp_head[1])

                    # AGGRESSIVE: Head-on collision advantage
                    if dist_to_opp == 1 and my_length > opp_length:
                        score += 3000  # Go for the kill!

                    # Chase them down
                    score += (20 - min(dist_to_opp, 20)) * 50  # Was 15, now 50

                    # Block their path to food
                    if best_food:
                        opp_dist_to_food = abs(opp_head[0] - best_food["x"]) + abs(opp_head[1] - best_food["y"])
                        my_dist_to_food = abs(new_x - best_food["x"]) + abs(new_y - best_food["y"])
                        if my_dist_to_food < opp_dist_to_food:
                            score += 500  # Block them from food

            elif my_length < opp_length - 2:  # Was -3, now -2 - more defensive
                # We're shorter - ESCAPE AND SURVIVE!
                opp_head = opponent_snake["body"][0] if opponent_snake else None
                if opp_head:
                    dist_to_opp = abs(new_x - opp_head[0]) + abs(new_y - opp_head[1])

                    # PANIC MODE: Stay far away
                    if dist_to_opp < 4:  # Danger zone
                        score -= 1000  # Heavy penalty
                    elif dist_to_opp < 8:
                        score -= 300  # Still avoid

                    # Find safe zones - prefer moves that maximize distance
                    score += dist_to_opp * 10  # Reward distance

                    # Tail chasing when no food nearby
                    if not best_food or best_food_dist > 8:
                        my_tail = my_snake["body"][-1]
                        tail_dist = abs(new_x - my_tail[0]) + abs(new_y - my_tail[1])
                        if tail_dist <= 2:  # Close to tail
                            score += 200  # Follow tail for safety

            # === Factor 4: Opponent threat level (ENHANCED ESCAPE) ===
            if threat_level > 50:  # Was 70, now 50 - more cautious
                # High threat from opponent - ESCAPE PROTOCOL ACTIVATED
                opp_head = opponent_snake["body"][0]
                opp_pred = self.predict_opponent_position(opponent_snake, steps=3)

                # Avoid predicted opponent positions - wider safety margin
                if opp_pred:
                    dist_to_pred = abs(new_x - opp_pred[0]) + abs(new_y - opp_pred[1])
                    if dist_to_pred < 4:  # Was 3, now 4
                        score -= 500  # Was 200, now 500

                # Extra safety: avoid being next to opponent
                dist_to_opp = abs(new_x - opp_head[0]) + abs(new_y - opp_head[1])
                if dist_to_opp <= 2 and my_length <= opp_length:
                    score -= 800  # Critical danger

                # When in danger, prioritize moves with maximum escape routes
                if threat_level > 80:
                    score += reachable * 5  # Extra bonus for open spaces

            # === Factor 5: Center preference (mid-game strategy) ===
            # Staying in center gives more escape routes
            center_x = self.grid_width / 2
            center_y = self.grid_height / 2
            dist_to_center = abs(new_x - center_x) + abs(new_y - center_y)
            score += (self.grid_width - dist_to_center) * 2

            # === Factor 6: Avoid edges ===
            edge_dist = min(new_x, self.grid_width - 1 - new_x,
                           new_y, self.grid_height - 1 - new_y)
            score += edge_dist * 5

            # === Factor 7: Survival Mode (No Food Available) ===
            if not foods or (best_food and best_food_dist > 12):
                # No food nearby - survival strategies
                my_tail = my_snake["body"][-1]

                # Tail chasing: follow your own tail for safety
                tail_dist = abs(new_x - my_tail[0]) + abs(new_y - my_tail[1])
                if tail_dist <= 3:  # Close to tail
                    score += 150  # Safe circular movement

                # When no food, prefer moves that maintain space
                if threat_level < 30:  # Only when not in immediate danger
                    score += reachable * 3  # Keep options open

            # === Factor 8: Food Blocking (Advanced Strategy) ===
            if opponent_snake and best_food:
                opp_head = opponent_snake["body"][0]
                opp_dist_to_food = abs(opp_head[0] - best_food["x"]) + abs(opp_head[1] - best_food["y"])
                my_dist_to_food = abs(new_x - best_food["x"]) + abs(new_y - best_food["y"])

                # If we can reach food before opponent, prioritize it
                if my_dist_to_food < opp_dist_to_food and my_length >= opp_length:
                    score += 300

                # Block opponent from food when we're longer
                elif my_length > opp_length and opp_dist_to_food <= 5:
                    # Position between opponent and food
                    blocking_score = 0
                    if abs(new_x - opp_head[0]) + abs(new_y - opp_head[1]) < opp_dist_to_food:
                        blocking_score = 200
                    score += blocking_score

            # Update best move
            if score > best_score:
                best_score = score
                best_dir = direction

        return best_dir if best_dir else safe_moves[0]["direction"]


# ============================================================================
#  MAIN
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(description="Advanced CopperHead Bot - Magic")
    parser.add_argument("--server", "-s", default=GAME_SERVER,
                        help=f"Server WebSocket URL (default: {GAME_SERVER})")
    parser.add_argument("--name", "-n", default=None,
                        help=f"Bot display name (default: {BOT_NAME})")
    parser.add_argument("--difficulty", "-d", type=int, default=5,
                        help="AI difficulty level 1-10 (for compatibility)")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress console output")
    args = parser.parse_args()

    bot = MagicBot(args.server, name=args.name)

    print(f"\n🔥 AGGRESSIVE MagicBot v2.0 - Ultra Offensive AI 🔥")
    print(f"  Server: {args.server}")
    print(f"  Features: Ultra-aggressive food pursuit | Opponent hunting")
    print(f"  Strategy: Grapes priority | Head-on attacks | Advanced escape")
    print()

    await bot.play()


if __name__ == "__main__":
    asyncio.run(main())
