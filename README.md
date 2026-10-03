# SYRUP

**You have no weapon. You have momentum.**

No attack button. Only dash. Pass *through* an enemy to **MARK** it, dash into the mark again to **DETONATE** it and win your energy back — play it right and you never stop moving.

Built with Python + pygame, single file.

## Mechanics

| | |
|---|---|
| **DASH** | Costs 1 energy, moves through enemies |
| **MARK** | Passing through an enemy leaves a mark |
| **DETONATE** | Dash into a mark to blow it up, refunds **2 energy** |
| **SHADOW** | Every dash leaves one behind — teleport into it anytime |
| **CANCEL** | Dash again within 6 frames of landing to erase recovery. **1.4×** score after |
| **PERFECT SWAP** | Swap while an enemy is touching you — time slows down |

Energy caps at 3, detonation refunds 2. **Chain it right and you never stop. Miss, and the world catches up.**

## Controls

| Key | Action |
|---|---|
| Mouse move | Aim / set dash direction |
| Left click / `SPACE` | Dash |
| `SHIFT` | Swap with nearest shadow |
| `R` | Restart |
| `ESC` | Menu / pause |
| `TAB` | Training mode |
| `F11` / `Alt+Enter` | Toggle fullscreen |

## Content

- **5 training stages** — unlocks dash, detonate, swap, cancel and perfect swap one at a time
- **RUN** — unlocked after training. Endless waves, chase your high score
- **5 materials** — Syrup / Mercury / Bubble / Oil / Ink, each with its own trail and afterimage
- **Tunable FX** — trail shape, afterimage, energy glow, detonation feedback, swap residue, floating verses

## Run it

```bash
pip install -r requirements.txt
python main.py
```

**Requires:** Python 3.10+ · pygame 2.6+ · numpy　　**Platform:** Windows / macOS / Linux

Saves are written to the system data directory (`%LOCALAPPDATA%\SYRUP\` on Windows). Chinese text falls back to a system CJK font automatically if no font file is bundled.

## License

[MIT](LICENSE) — use, modify and sell it freely.


# SYRUP / 糖浆

**You have no weapon. You have momentum.**

没有攻击键，只有冲刺。穿过敌人留下**标记**，再冲一次**引爆**它并回收能量——打得好就永远停不下来。

Python + pygame 单文件。

## 玩法

| | |
|---|---|
| **冲刺** | 消耗 1 能量，高速穿过敌人 |
| **标记** | 穿过敌人即留下标记 |
| **引爆** | 对标记再冲一次，引爆并返还 **2 能量** |
| **影** | 每次冲刺留下残影，可随时换位 |
| **取消** | 落地 6 帧内再冲，取消后摇，得分 **1.4×** |
| **完美换位** | 敌人贴身时换位，触发慢动作 |

能量上限 3，引爆回 2 —— **打得好就停不下来，打空了只能跑**。

## 操作

| 按键 | 功能 |
|---|---|
| 鼠标移动 | 瞄准 / 决定冲刺方向 |
| 鼠标左键 / `SPACE` | 冲刺 |
| `SHIFT` | 与最近的影换位 |
| `R` | 重开 |
| `ESC` | 菜单 / 暂停 |
| `TAB` | 练习模式 |
| `F11` / `Alt+Enter` | 全屏切换 |

## 内容

- **5 个训练关卡** —— 逐个解锁冲刺、引爆、换位、取消、完美换位
- **实战模式** —— 通关训练后解锁，无限波次追分
- **5 种材质** —— 糖浆 / 水银 / 气泡 / 油 / 墨，各有独立拖尾与残影表现
- **可调特效** —— 拖尾形态、残影、能量微光、引爆反馈、换位残留、诗句浮现

## 运行

```bash
pip install -r requirements.txt
python main.py
```

**环境**：Python 3.10+ · pygame 2.6+ · numpy　　**平台**：Windows / macOS / Linux

存档自动写入系统数据目录（Windows 为 `%LOCALAPPDATA%\SYRUP\`）。中文字体缺失时自动回退系统字体。

## 许可

[MIT](LICENSE) — 可自由使用、修改、商用。
