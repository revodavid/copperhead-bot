# CopperHead Bot

A starter template for building your own AI bot to compete in [CopperHead](https://github.com/revodavid/copperhead-server) Snake tournaments.

## Quick Start

### 1. Set up your environment

You can develop your bot in **GitHub Codespaces** (recommended) or locally.

**Option A: GitHub Codespaces** (no setup required)
- Fork this repository and open it in a Codespace.
- Dependencies are installed automatically.

**Option B: Local development**
- Make sure you have Python 3.10+ installed.
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

### 2. Run your bot

```bash
python mybot.py --server ws://localhost:8765/ws/
```

For a CopperHead server running in Codespaces, use the `wss://` URL shown in the terminal:
```bash
python mybot.py --server wss://your-codespace-url.app.github.dev/ws/
```

### 3. Customize your bot

Open `mybot.py` and look for the `calculate_move()` function (around line 200). This is where your bot decides which direction to move each tick. The default strategy is simple — chase food and avoid walls. You can do much better!

## Command Line Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--server` | `-s` | `ws://localhost:8765/ws/` | Server WebSocket URL |
| `--name` | `-n` | `MyBot` | Your bot's display name |

## How It Works

Your bot connects to a CopperHead server via WebSocket and plays Snake automatically. Every game tick, the server sends the current game state and your bot responds with a direction to move.

### Game State

Each tick, the server sends a `state` message containing:

```json
{
  "running": true,
  "grid": { "width": 20, "height": 16 },
  "snakes": {
    "1": {
      "body": [[10, 5], [9, 5], [8, 5]],
      "direction": "right",
      "alive": true
    },
    "2": {
      "body": [[15, 10], [16, 10]],
      "direction": "left",
      "alive": true
    }
  },
  "foods": [
    { "x": 5, "y": 8, "type": "apple" }
  ]
}
```

Key details:
- **Grid**: `(0, 0)` is the top-left corner. `y` increases downward.
- **Snake body**: Array of `[x, y]` positions. The head is the first element.
- **Foods**: Array of food items with position and type.

### Your Bot's Move

Your `calculate_move()` function returns one of: `"up"`, `"down"`, `"left"`, `"right"`.

Rules:
- You **cannot reverse** direction (e.g., can't go `"left"` if currently going `"right"`).
- If you hit a wall or a snake (including yourself), you lose the point.
- Eating food (especially apples 🍎) makes your snake grow longer.

### Tournament Flow

1. Your bot joins a tournament and waits for an opponent.
2. Matches are best-of-N games (set by the server).
3. Match winners advance to the next round.
4. Losers are eliminated. The last bot standing wins! 🏆

## Strategy Ideas

Here are some ways to improve your bot beyond the basic "chase food" strategy:

- **Flood fill**: Before moving, count how many squares are reachable from each direction. Avoid moves that lead into small enclosed spaces.
- **Opponent prediction**: Look at the opponent's direction and predict where they'll go. Avoid head-on collisions (unless you're longer!).
- **Food blocking**: Position yourself between the opponent and the food.
- **Length awareness**: Play more aggressively when you're longer than your opponent, more defensively when shorter.
- **Tail chasing**: When no food is nearby, follow your own tail to stay safe.

## Using AI to Help You Code

You don't need to be an expert programmer to build a winning bot! AI coding assistants can help:

- **[GitHub Copilot CLI](https://github.com/features/copilot/cli/)**: Run `copilot` in your terminal and describe the strategy you want in plain English.
- **[GitHub Copilot](https://github.com/features/copilot)**: Works in the GitHub web editor and VS Code with inline suggestions.

Example prompt for Copilot CLI:
```
modify mybot.py to use flood fill to avoid getting trapped in dead ends
```

## File Structure

```
copperhead-bot/
├── mybot.py           # Your bot — edit this!
├── requirements.txt   # Python dependencies
├── README.md          # This file
└── .gitignore         # Git ignore rules
```

## Server Reference

For full details on the game rules, server messages, and competition logic, see the [CopperHead Server documentation](https://github.com/revodavid/copperhead-server):

- [How to Build Your Own Bot](https://github.com/revodavid/copperhead-server/blob/main/How-To-Build-Your-Own-Bot.md) — full message protocol reference
- [Game Rules](https://github.com/revodavid/copperhead-server/blob/main/game-rules.md) — collision rules, food types, and buffs
- [Competition Logic](https://github.com/revodavid/copperhead-server/blob/main/competition-logic.md) — tournament format and matchmaking
