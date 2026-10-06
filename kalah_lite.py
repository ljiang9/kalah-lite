#!/usr/bin/env python3
"""Kalah（卡拉哈，播棋家族）极简实现。

规则（标准 Kalah 6-6 版）:
- 2x6 坑 + 2 个计分仓（Kalah）。开局每坑 4 子。
- 轮到一方，从自己一侧任一非空坑抓起全部子，逆时针逐坑播一子，
  经过自己的计分仓时放一子，跳过对方的计分仓。
- 最后一子落入自己计分仓 -> 再走一步。
- 最后一子落入自己一侧的空坑，且对面坑有子 -> 吃掉对面坑全部子
  和本坑这一子，一起进自己的计分仓。
- 一方六坑全空时游戏结束；另一方把自己一侧剩余子全部扫入自己的仓，
  仓中子多者胜。

纯标准库，Python 3.10+。
"""

from __future__ import annotations

import argparse
import copy
import random
import sys

PITS = 6          # 每侧坑数
START_SEEDS = 4   # 开局每坑子数
MAX_PLIES = 400   # 防无限对局的半回合上限

SOUTH, NORTH = 0, 1  # 南方（先手）/北方


class Kalah:
    """Kalah 对局状态。棋盘: pits[side][0..5]，stores[side] 计分仓。"""

    def __init__(self):
        self.pits = [[START_SEEDS] * PITS for _ in range(2)]
        self.stores = [0, 0]
        self.turn = SOUTH

    def clone(self):
        return copy.deepcopy(self)

    # ---- 走法 ----

    def legal_moves(self, side=None):
        side = self.turn if side is None else side
        return [i for i in range(PITS) if self.pits[side][i] > 0]

    def _check_move(self, side, pit):
        if side not in (SOUTH, NORTH):
            raise ValueError(f"非法方: {side}")
        if not (0 <= pit < PITS):
            raise ValueError(f"坑号越界: {pit}")
        if self.pits[side][pit] == 0:
            raise ValueError(f"空坑不能走: {pit}")

    def apply_move(self, pit):
        """当前方走 pit。返回 (extra_turn: bool)。非法抛 ValueError。

        播种顺序（逆时针）: 己方坑 pit+1..5 -> 己方仓 -> 对方坑 0..5 ->
        己方坑 0..pit-1 -> 己方仓 ...（跳过对方仓）。
        """
        side = self.turn
        self._check_move(side, pit)
        seeds = self.pits[side][pit]
        self.pits[side][pit] = 0
        foe = 1 - side

        # 线性化播种轨道: 己方坑 pit+1..5, 己方仓, 对方坑 0..5, 己方坑 0..pit-1 ...
        # 用 (kind, idx) 表示: ("pit", side, i) / ("store", side)
        track = []
        for i in range(pit + 1, PITS):
            track.append(("pit", side, i))
        track.append(("store", side))
        for i in range(PITS):
            track.append(("pit", foe, i))
        for i in range(pit):
            track.append(("pit", side, i))

        pos = 0
        last = None
        while seeds:
            kind = track[pos % len(track)]
            if kind[0] == "pit":
                _, s, i = kind
                self.pits[s][i] += 1
            else:
                _, s = kind
                self.stores[s] += 1
            last = kind
            seeds -= 1
            pos += 1

        extra_turn = last == ("store", side)

        # 吃子: 落入己方空坑（播之前是空的）且对面有子
        if last[0] == "pit" and last[1] == side:
            _, _, i = last
            opp = PITS - 1 - i
            if self.pits[side][i] == 1 and self.pits[foe][opp] > 0:
                captured = self.pits[foe][opp] + 1
                self.pits[foe][opp] = 0
                self.pits[side][i] = 0
                self.stores[side] += captured

        if not extra_turn:
            self.turn = foe
        return extra_turn

    # ---- 终局 ----

    def is_over(self):
        return all(s == 0 for s in self.pits[SOUTH]) or all(s == 0 for s in self.pits[NORTH])

    def final_sweep(self):
        """终局扫子: 各方把自己一侧剩余子扫入自己的仓。"""
        for side in (SOUTH, NORTH):
            self.stores[side] += sum(self.pits[side])
            self.pits[side] = [0] * PITS

    def winner(self):
        """返回 SOUTH / NORTH / None(平局)。调用前建议先 final_sweep。"""
        if self.stores[SOUTH] > self.stores[NORTH]:
            return SOUTH
        if self.stores[NORTH] > self.stores[SOUTH]:
            return NORTH
        return None


# ---- AI ----

def ai_move(game: Kalah, rng: random.Random) -> int:
    """贪心: 优先能再走一步，其次吃子最多，其次仓子多，平局随机。"""
    side = game.turn
    best, best_key = None, None
    for pit in game.legal_moves():
        g = game.clone()
        store_before = g.stores[side]
        extra = g.apply_move(pit)
        gained = g.stores[side] - store_before
        key = (1 if extra else 0, gained)
        if best_key is None or key > best_key or (key == best_key and rng.random() < 0.5):
            best, best_key = pit, key
    return best


def play_auto(games=10, seed=42, verbose=False):
    rng = random.Random(seed)
    tally = {SOUTH: 0, NORTH: 0, None: 0}
    for gi in range(games):
        g = Kalah()
        plies = 0
        while not g.is_over() and plies < MAX_PLIES:
            mv = ai_move(g, rng)
            if mv is None:
                break
            g.apply_move(mv)
            plies += 1
        g.final_sweep()
        w = g.winner()
        tally[w] += 1
        if verbose or gi >= games - 3:
            wn = "南胜" if w == SOUTH else ("北胜" if w == NORTH else "平局")
            print(f"第 {gi+1}/{games} 局：{wn}（{g.stores[SOUTH]}:{g.stores[NORTH]}）")
    print(f"总计：南胜 {tally[SOUTH]}，北胜 {tally[NORTH]}，平局 {tally[None]}")
    return tally


# ---- 渲染与交互 ----

def render(g: Kalah) -> str:
    top = " ".join(f"{s:2d}" for s in g.pits[NORTH][::-1])
    bot = " ".join(f"{s:2d}" for s in g.pits[SOUTH])
    lines = [
        f"      北方坑（右→左）",
        f"北仓 {g.stores[NORTH]:2d} | {top} |",
        f"南仓 {g.stores[SOUTH]:2d} | {bot} |",
        f"      南方坑（左→右 0-5）",
        f"轮到：{'南方(你)' if g.turn == SOUTH else '北方(AI)'}",
    ]
    return "\n".join(lines)


def play_interactive(seed=None):
    if not sys.stdin.isatty():
        print("交互模式需要终端；无头演示请用 --auto", file=sys.stderr)
        return 2
    rng = random.Random(seed)
    g = Kalah()
    print("Kalah 卡拉哈：你是南方（下面一排），输入坑号 0-5 走子，q 退出。")
    while not g.is_over():
        print(render(g))
        if g.turn == SOUTH:
            try:
                raw = input("走哪个坑 (0-5)? ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n已退出。")
                return 0
            if raw.lower() == "q":
                print("已退出。")
                return 0
            try:
                pit = int(raw)
                extra = g.apply_move(pit)
            except (ValueError, IndexError) as e:
                print(f"非法走法：{e}")
                continue
            if extra:
                print("最后一子落入计分仓，再走一步！")
        else:
            mv = ai_move(g, rng)
            extra = g.apply_move(mv)
            print(f"北方走坑 {mv}" + ("，再走一步" if extra else ""))
    g.final_sweep()
    print(render(g))
    w = g.winner()
    print("你赢了！" if w == SOUTH else ("AI 赢了。" if w == NORTH else "平局。"))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Kalah 卡拉哈（播棋）")
    ap.add_argument("--auto", action="store_true", help="AI 对 AI 自动演示")
    ap.add_argument("--games", type=int, default=10, help="自动演示局数")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--verbose", action="store_true", help="打印每局过程")
    args = ap.parse_args(argv)
    if args.auto:
        play_auto(args.games, args.seed, args.verbose)
        return 0
    return play_interactive(args.seed)


if __name__ == "__main__":
    sys.exit(main())
