# Exploding Kittens – Streamlit Terminal-Style UI

"""
Streamlit app: terminal-like UI + clickable cards.
Features:
 - Dark, "terminal" style UI with custom CSS
 - Terminal pane showing game log (append-only)
 - Command input (draw, play <card>, pair <cat>, trio <cat>, help)
 - Clickable card buttons to play a card directly (like typing 'play <card>')
 - AI heuristics, Nope handling, Defuse, Exploding Kittens
 - Local stats saved to ek_streamlit_stats.json

Save as `exploding_kittens_streamlit.py` and run `streamlit run exploding_kittens_streamlit.py`.
"""

import streamlit as st
import random
import json
import os
import time

CARD_TYPES = {
    "Exploding Kitten": 1,
    "Defuse": 3,
    "Nope": 6,
    "Taco Cat": 7,
    "Beard Cat": 7,
    "Rainbow Ralphing Cat": 7,
    "Skip": 4,
    "Attack": 4,
    "See the Future": 4,
    "Favor": 3,
    "Shuffle": 3,
    "Peek": 1,
    "Unlucky": 2,
}
CAT_CARDS = ["Taco Cat", "Beard Cat", "Rainbow Ralphing Cat"]
STATS_FILE = "ek_streamlit_stats.json"

# ----------------- Utilities -----------------

def sort_hand(hand):
    order = [
        'Defuse', 'Nope', 'Skip', 'Attack', 'See the Future', 'Peek', 'Favor', 'Shuffle', 'Unlucky',
        'Taco Cat', 'Beard Cat', 'Rainbow Ralphing Cat'
    ]
    return sorted(hand, key=lambda c: order.index(c) if c in order else 99)


def save_stats(stats):
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f)
    except Exception:
        pass


def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"games_played": 0, "player_wins": 0, "ai_wins": 0}
    return {"games_played": 0, "player_wins": 0, "ai_wins": 0}


def find_matching_card(hand, query):
    q = query.strip().lower()
    for c in hand:
        if c.lower() == q:
            return c
    for c in hand:
        if c.lower().startswith(q):
            return c
    for c in hand:
        if q in c.lower():
            return c
    return None

# ----------------- Game Engine -----------------

def init_game(player_name="Player"):
    ss = st.session_state
    ss.history = ["--- New game started ---"]
    ss.discard_pile = []
    ss.players = {"Player": [], "AI": []}
    ss.turn = "Player"
    ss.game_over = False
    ss.attack_turns = 0
    ss.player_name = player_name
    ss.seen_top_cards = []
    ss.winner = None
    ss.pending_action = None
    ss.ai_pending = None
    ss.player_ready_to_resolve = False

    temp = []
    for card, cnt in CARD_TYPES.items():
        if card not in ("Exploding Kitten", "Defuse"):
            temp.extend([card] * cnt)
    random.shuffle(temp)

    for p in ss.players:
        hand = []
        for _ in range(4):
            if temp:
                hand.append(temp.pop())
        hand.append("Defuse")
        random.shuffle(hand)
        ss.players[p] = hand

    remaining = temp[:]
    kittens = max(1, len(ss.players) - 1)
    remaining.extend(["Exploding Kitten"] * kittens)
    total_def = CARD_TYPES.get("Defuse", 0)
    remaining_def = max(0, total_def - len(ss.players))
    remaining.extend(["Defuse"] * remaining_def)
    random.shuffle(remaining)
    ss.deck = remaining
    ss.seen_top_cards = []
    ss.stats = load_stats()


def append_log(text):
    ss = st.session_state
    ss.history.append(text)


def draw_card(player):
    ss = st.session_state
    if ss.game_over:
        return
    if not ss.deck:
        if not ss.discard_pile:
            ss.game_over = True
            ss.winner = "AI" if player == "Player" else "Player"
            append_log(f"Deck and discard empty. {ss.winner} wins.")
            return
        ss.deck = ss.discard_pile[:]
        ss.discard_pile = []
        random.shuffle(ss.deck)
        append_log("Shuffled discard back into deck.")

    card = ss.deck.pop(0)
    append_log(f"{player} drew: {card}")

    if card == "Unlucky":
        hand = ss.players[player]
        if not hand:
            append_log(f"{player} has no cards to discard.")
            return
        if player == "AI":
            non_defuse = [c for c in hand if c != "Defuse"]
            lost = random.choice(non_defuse) if non_defuse else hand[0]
            hand.remove(lost)
            ss.discard_pile.append(lost)
            append_log(f"AI discarded {lost} due to Unlucky.")
        else:
            non_defuse = [c for c in hand if c != "Defuse"]
            lost = non_defuse[0] if non_defuse else hand[0]
            hand.remove(lost)
            ss.discard_pile.append(lost)
            append_log(f"You discarded {lost} due to Unlucky.")
        return

    if card == "Exploding Kitten":
        if "Defuse" in ss.players[player]:
            ss.players[player].remove("Defuse")
            ss.discard_pile.append("Defuse")
            idx = random.randint(0, len(ss.deck))
            ss.deck.insert(idx, "Exploding Kitten")
            append_log(f"{player} used Defuse. Kitten returned to deck.")
            ss.seen_top_cards = []
            return
        else:
            ss.game_over = True
            ss.winner = "Player" if player == "AI" else "AI"
            append_log(f"{player} exploded! {ss.winner} wins.")
            return
    else:
        ss.players[player].append(card)


def try_nope_responses(actor, card_name):
    ss = st.session_state
    defender = "AI" if actor == "Player" else "Player"

    # If defender is AI, AI may decide to Nope immediately
    if defender == "AI" and "Nope" in ss.players["AI"]:
        if ai_decide_nope(card_name):
            ss.players["AI"].remove("Nope")
            ss.discard_pile.append("Nope")
            append_log("AI used Nope!")
            # allow player to respond with Nope (UI shows button)
            if "Nope" in ss.players["Player"]:
                ss.pending_action = {"actor": actor, "card": card_name, "noped_by": "AI"}
                ss.player_ready_to_resolve = True
                ss.ai_pending = card_name
                return False
            return False
    # Defender is Player: UI will prompt player for Nope
    if defender == "Player" and "Nope" in ss.players["Player"]:
        ss.pending_action = {"actor": actor, "card": card_name, "noped_by": None}
        ss.player_ready_to_resolve = True
        return False
    return True


def ai_decide_nope(card_name):
    strong = ["Attack", "Favor", "Peek", "Shuffle", "See the Future", "Skip"]
    if any(s in card_name for s in strong):
        return random.random() < 0.7
    return random.random() < 0.03


def execute_card_effect(player, card):
    ss = st.session_state
    append_log(f"{player} plays {card}.")
    ss.discard_pile.append(card)

    if card == "Peek":
        target = "AI" if player == "Player" else "Player"
        peek_hand = ss.players[target][:3]
        if player == "Player":
            append_log(f"You peek at {target}'s first 3 cards: {peek_hand}")
        else:
            append_log("AI peeks at your cards.")
        return False

    if card == "Skip":
        append_log(f"{player}'s turn is skipped.")
        return True

    if card == "Attack":
        ss.attack_turns = ss.attack_turns + 1 if ss.attack_turns else 2
        append_log(f"Attack played: next player must take 2 turns.")
        return True

    if card == "See the Future":
        ss.seen_top_cards = ss.deck[:3]
        if player == "Player":
            append_log(f"THE FUTURE: {ss.seen_top_cards}")
        else:
            append_log("AI sees the top cards.")
        return False

    if card == "Favor":
        target = "AI" if player == "Player" else "Player"
        if ss.players[target]:
            if target == "AI":
                ai_hand_non_precious = [c for c in ss.players["AI"] if c not in ("Defuse", "Nope")]
                ai_gift = random.choice(ai_hand_non_precious) if ai_hand_non_precious else random.choice(ss.players["AI"])
                ss.players["AI"].remove(ai_gift)
                ss.players[player].append(ai_gift)
                append_log(f"AI gives {player} {ai_gift}.")
            else:
                if ss.players["Player"]:
                    gave = ss.players["Player"].pop(0)
                    ss.players["AI"].append(gave)
                    append_log(f"You gave AI {gave} (Favor fallback).")
        return False

    if card == "Shuffle":
        random.shuffle(ss.deck)
        append_log("Deck shuffled.")
        return False

    return False


def player_play_card(card):
    ss = st.session_state
    if card not in ss.players["Player"]:
        append_log("Card not in hand.")
        return
    if card == "Defuse":
        append_log("Defuse can only be used when you draw an Exploding Kitten.")
        return
    if card == "Nope":
        append_log("Nope cannot be played proactively here.")
        return

    ss.players["Player"].remove(card)
    survives = try_nope_responses("Player", card)
    if not survives:
        append_log("Your play was NOPED.")
        ss.discard_pile.append(card)
        ss.pending_action = None
        return
    ended = execute_card_effect("Player", card)
    if ended:
        ss.turn = "AI"
    else:
        # player must draw unless Skip/Attack handled
        draw_card("Player")
        ss.turn = "AI"


def player_pair(cat):
    ss = st.session_state
    if ss.players["Player"].count(cat) < 2:
        append_log(f"You don't have two {cat}s.")
        return
    for _ in range(2):
        ss.players["Player"].remove(cat)
        ss.discard_pile.append(cat)
    if ss.players["AI"]:
        stolen = random.choice(ss.players["AI"])
        ss.players["AI"].remove(stolen)
        ss.players["Player"].append(stolen)
        append_log(f"You played pair of {cat}s and stole {stolen} from AI.")
    else:
        append_log("AI has no cards to steal.")


def player_trio(cat, requested_card):
    ss = st.session_state
    if ss.players["Player"].count(cat) < 3:
        append_log(f"You don't have three {cat}s.")
        return
    for _ in range(3):
        ss.players["Player"].remove(cat)
        ss.discard_pile.append(cat)
    found = None
    for c in ss.players["AI"]:
        if requested_card.lower() in c.lower():
            found = c
            break
    if found:
        ss.players["AI"].remove(found)
        ss.players["Player"].append(found)
        append_log(f"AI had {found}. You take it.")
    else:
        append_log("AI does not have that card.")


def ai_take_turn():
    ss = st.session_state
    if ss.game_over:
        return
    top3 = ss.seen_top_cards if ss.seen_top_cards else ss.deck[:3]
    prob_kitten = "Exploding Kitten" in top3
    hand = ss.players["AI"]

    for danger in ("Skip", "Shuffle", "Attack"):
        if prob_kitten and danger in hand:
            hand.remove(danger)
            ss.discard_pile.append(danger)
            ss.pending_action = {"actor": "AI", "card": danger}
            ss.ai_pending = danger
            ss.player_ready_to_resolve = True
            append_log(f"AI intends to play {danger} (awaiting resolution).")
            return

    if "See the Future" in hand and not ss.seen_top_cards and random.random() < 0.6:
        hand.remove("See the Future")
        ss.discard_pile.append("See the Future")
        ss.seen_top_cards = ss.deck[:3]
        append_log("AI plays See the Future and views top cards.")
        return

    for cat in CAT_CARDS:
        if hand.count(cat) >= 2:
            for _ in range(2):
                hand.remove(cat)
                ss.discard_pile.append(cat)
            if ss.players["Player"]:
                priority = ["Defuse", "Nope", "Attack", "Favor", "Peek"]
                stolen = None
                for p in priority:
                    if p in ss.players["Player"]:
                        ss.players["Player"].remove(p)
                        hand.append(p)
                        stolen = p
                        break
                if not stolen:
                    stolen = ss.players["Player"].pop(0)
                    hand.append(stolen)
                append_log(f"AI played a pair of {cat}s and stole {stolen}.")
                return

    if "Favor" in hand and (len(hand) < 8 or random.random() < 0.2):
        hand.remove("Favor")
        ss.discard_pile.append("Favor")
        if ss.players["Player"]:
            non_precious = [c for c in ss.players["Player"] if c not in ("Defuse", "Nope")]
            stolen = random.choice(non_precious) if non_precious else ss.players["Player"].pop(0)
            ss.players["Player"].remove(stolen)
            hand.append(stolen)
            append_log(f"AI played Favor and took your {stolen}.")
            return

    if "Shuffle" in hand and len(ss.deck) < 5:
        hand.remove("Shuffle")
        ss.discard_pile.append("Shuffle")
        random.shuffle(ss.deck)
        append_log("AI shuffled the deck.")
        return

    draw_card("AI")

# ----------------- Streamlit UI -----------------

STYLE = """
<style>
body { background-color: #0b0f1a; color: #e6eef6; }
.stApp { background-color: #0b0f1a; }
.card { display:inline-block; margin:6px; padding:10px 14px; border-radius:12px; box-shadow: 0 6px 14px rgba(0,0,0,0.7); background: linear-gradient(180deg,#16202b,#0f1720); border:1px solid rgba(255,255,255,0.04); }
.card .title { font-weight:700; font-size:14px; }
.terminal { background:#020306; color:#cfeff8; padding:12px; border-radius:8px; font-family: monospace; height:300px; overflow:auto; border:1px solid rgba(255,255,255,0.03); }
.small { font-size:12px; color:#9fbecb }
.btn-card { background: linear-gradient(180deg,#213244,#14202b); color: #e9fbff; border-radius:10px; padding:8px 10px; }
</style>
"""


def main():
    st.set_page_config(page_title="Exploding Kittens — Terminal UI", layout="wide")
    st.markdown(STYLE, unsafe_allow_html=True)

    if 'deck' not in st.session_state:
        st.session_state.clear()
        name = st.text_input("Enter your player name:", value="Player")
        if st.button("Start game"):
            init_game(name.strip() or "Player")
            st.experimental_rerun()
        st.stop()

    ss = st.session_state

    header_col1, header_col2 = st.columns([3,1])
    with header_col1:
        st.markdown(f"# 🎴 Exploding Kittens — {ss.player_name}")
    with header_col2:
        st.markdown(f"**Deck:** {len(ss.deck)}  \\n**Discard:** {len(ss.discard_pile)}")

    left, right = st.columns([2,3])

    with left:
        st.markdown("### Your hand")
        hand = sort_hand(ss.players['Player'])
        cols = st.columns(4)
        for i, card in enumerate(hand):
            with cols[i % 4]:
                if st.button(card, key=f"card_{i}"):
                    player_play_card(card)
                    if not ss.game_over:
                        ss.turn = 'AI'
                    st.experimental_rerun()

        st.markdown("---")
        st.markdown("**Commands (terminal):** draw | play <card> | pair <cat> | trio <cat> | help")
        cmd = st.text_input("Terminal input (type a command and press Enter)", key='cmd_input')
        if cmd:
            parts = cmd.strip().split(maxsplit=1)
            cmd0 = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""
            if cmd0 == 'help':
                append_log("Commands: draw, play <card>, pair <cat>, trio <cat>, help")
            elif cmd0 == 'draw':
                draw_card('Player')
                ss.turn = 'AI'
            elif cmd0 == 'play':
                if not arg:
                    append_log('play <card>: missing card name')
                else:
                    pick = find_matching_card(ss.players['Player'], arg)
                    if pick:
                        player_play_card(pick)
                        ss.turn = 'AI'
                    else:
                        append_log(f"No matching card for '{arg}' in hand.")
            elif cmd0 == 'pair':
                pick = None
                for cat in CAT_CARDS:
                    if arg.lower() in cat.lower():
                        pick = cat
                        break
                if pick:
                    player_pair(pick)
                else:
                    append_log('pair <cat>: specify Taco/Beard/Rainbow')
            elif cmd0 == 'trio':
                pick = None
                for cat in CAT_CARDS:
                    if arg.lower() in cat.lower():
                        pick = cat
                        break
                if pick:
                    requested = st.text_input('Requested card for trio:', key='trio_req')
                    if requested:
                        player_trio(pick, requested)
                else:
                    append_log('trio <cat>: specify Taco/Beard/Rainbow')
            else:
                append_log('Unknown command. Type help for commands.')
            st.session_state.cmd_input = ''
            st.experimental_rerun()

        st.markdown('---')
        if ss.player_ready_to_resolve and ss.pending_action:
            pa = ss.pending_action
            st.warning(f"Pending: {pa['actor']} -> {pa['card']}")
            if pa.get('noped_by') == 'AI':
                st.info('AI has No-ped this action. You may respond with Nope if available.')
            if 'Nope' in ss.players['Player']:
                if st.button('Use Nope to cancel'):
                    ss.players['Player'].remove('Nope')
                    ss.discard_pile.append('Nope')
                    append_log('You used Nope. Action canceled.')
                    ss.pending_action = None
                    ss.player_ready_to_resolve = False
                    ss.ai_pending = None
                    st.experimental_rerun()
            if st.button('Resolve action'):
                pa = ss.pending_action
                if pa.get('noped_by') == 'AI':
                    append_log('AI had No-ped; action canceled.')
                else:
                    execute_card_effect(pa['actor'], pa['card'])
                ss.pending_action = None
                ss.player_ready_to_resolve = False
                ss.ai_pending = None
                st.experimental_rerun()

        st.markdown('---')
        if st.button('Show my full hand'):
            append_log(f"Hand: {ss.players['Player']}")

    with right:
        st.markdown('### Terminal')
        terminal_text = '\n'.join(ss.history[-200:])
        st.markdown(f"<div class='terminal'>\n{terminal_text.replace('\n','<br>')}\n</div>", unsafe_allow_html=True)

        st.markdown('---')
        st.markdown('### AI / Status')
        st.write(f"AI has {len(ss.players['AI'])} cards (hidden).")
        st.write(f"Seen top cards: {ss.seen_top_cards}")
        st.write(f"Your Defuse: {ss.players['Player'].count('Defuse')} | Nope: {ss.players['Player'].count('Nope')}")

        if ss.turn == 'AI' and not ss.player_ready_to_resolve and not ss.game_over:
            if st.button('Run AI turn'):
                ai_take_turn()
                if not ss.player_ready_to_resolve:
                    ss.turn = 'Player'
                st.experimental_rerun()

        if ss.game_over:
            st.success(f"Game Over: {ss.winner} wins!")
            stats = ss.stats
            stats['games_played'] = stats.get('games_played', 0) + 1
            if ss.winner == 'Player':
                stats['player_wins'] = stats.get('player_wins', 0) + 1
            else:
                stats['ai_wins'] = stats.get('ai_wins', 0) + 1
            save_stats(stats)
            if st.button('Restart'):
                init_game(ss.player_name)
                st.experimental_rerun()

    st.markdown('---')
    st.markdown('Tip: Click cards to play them quickly, or use the terminal input for command-style play.')


if __name__ == '__main__':
    main()
