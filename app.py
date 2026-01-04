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

# ---------- Utilities ----------

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


# ---------- Game State helpers ----------

def init_game(player_name="Player"):
    ss = st.session_state
    ss.history = []
    ss.discard_pile = []
    ss.players = {"Player": [], "AI": []}
    ss.turn = "Player"
    ss.game_over = False
    ss.attack_turns = 0
    ss.player_name = player_name
    ss.seen_top_cards = []
    ss.winner = None
    ss.pending_action = None  # dict with keys: actor, card, meta

    # Build a pool of non-defuse, non-kitten cards
    temp = []
    for card, cnt in CARD_TYPES.items():
        if card not in ("Exploding Kitten", "Defuse"):
            temp.extend([card] * cnt)
    random.shuffle(temp)

    # deal 4 + 1 Defuse to each player
    for p in ss.players:
        hand = []
        for _ in range(4):
            if temp:
                hand.append(temp.pop())
        hand.append("Defuse")
        random.shuffle(hand)
        ss.players[p] = hand

    # remaining deck: remaining temp + exploding kittens (players -1) + remaining defuses
    remaining = temp[:]
    kittens = max(1, len(ss.players) - 1)
    remaining.extend(["Exploding Kitten"] * kittens)
    total_def = CARD_TYPES.get("Defuse", 0)
    remaining_def = max(0, total_def - len(ss.players))
    remaining.extend(["Defuse"] * remaining_def)
    random.shuffle(remaining)
    ss.deck = remaining
    ss.discard_pile = []
    ss.seen_top_cards = []
    ss.attack_turns = 0
    ss.game_over = False
    ss.winner = None
    ss.player_ready_to_resolve = False
    ss.ai_pending = None
    ss.stats = load_stats()


# ---------- Core mechanics ----------

def log(msg):
    st.session_state.history.append(msg)


def draw_card(player):
    ss = st.session_state
    if not ss.deck:
        if not ss.discard_pile:
            ss.game_over = True
            ss.winner = "AI" if player == "Player" else "Player"
            log(f"Deck and discard empty. {ss.winner} wins.")
            return
        ss.deck = ss.discard_pile[:]
        ss.discard_pile = []
        random.shuffle(ss.deck)
        log("Shuffled discard back into deck.")

    card = ss.deck.pop(0)
    log(f"{player} drew: {card}")

    if card == "Unlucky":
        # must discard a card
        hand = ss.players[player]
        if not hand:
            log(f"{player} has no cards to discard.")
            return
        if player == "AI":
            non_defuse = [c for c in hand if c != "Defuse"]
            lost = random.choice(non_defuse) if non_defuse else hand[0]
            hand.remove(lost)
            ss.discard_pile.append(lost)
            log(f"AI discarded {lost} due to Unlucky.")
        else:
            # for player: automatically discard the first non-defuse if exists, else first
            non_defuse = [c for c in hand if c != "Defuse"]
            lost = non_defuse[0] if non_defuse else hand[0]
            hand.remove(lost)
            ss.discard_pile.append(lost)
            log(f"You discarded {lost} due to Unlucky.")
        return

    if card == "Exploding Kitten":
        if "Defuse" in ss.players[player]:
            # use defuse automatically
            ss.players[player].remove("Defuse")
            ss.discard_pile.append("Defuse")
            # place kitten back randomly
            idx = random.randint(0, len(ss.deck))
            ss.deck.insert(idx, "Exploding Kitten")
            log(f"{player} used Defuse. Kitten returned to deck.")
            ss.seen_top_cards = []
            return
        else:
            ss.game_over = True
            ss.winner = "Player" if player == "AI" else "AI"
            log(f"{player} exploded! {ss.winner} wins.")
            return
    else:
        ss.players[player].append(card)


def try_nope_responses(actor, card_name):
    """
    Resolve the possibility of a Nope chain when actor plays card_name.
    Returns True if the action survives (i.e., not fully NOPED away).
    """
    ss = st.session_state
    pending = {"actor": actor, "card": card_name}
    # start with defender: the other side
    defender = "AI" if actor == "Player" else "Player"

    # simple chain: allow AI to auto-NOPE and allow player to click a button in UI to Nope AI plays
    # 1) If defender is AI, check AI heuristics
    if defender == "AI":
        # AI may nope based on heuristics
        if "Nope" in ss.players["AI"]:
            use = ai_decide_nope(card_name)
            if use:
                ss.players["AI"].remove("Nope")
                ss.discard_pile.append("Nope")
                log("AI used Nope!")
                # actor may respond with player's Nope if available
                if "Nope" in ss.players["Player"]:
                    # give player choice: automatically use it if streamlit button clicked
                    ss.pending_action = {"actor": actor, "card": card_name, "noped_by": "AI"}
                    ss.player_ready_to_resolve = True
                    ss.ai_pending = None
                    return False
                else:
                    # chain ends, action is noped
                    return False
    else:
        # defender is Player: if player has Nope, they may press button in UI
        if "Nope" in ss.players["Player"]:
            # reveal UI choice by setting pending_action so UI can show a 'Use Nope' button
            ss.pending_action = {"actor": actor, "card": card_name, "noped_by": None}
            ss.player_ready_to_resolve = True
            ss.ai_pending = None
            return False
    return True


def ai_decide_nope(card_name):
    # heuristic: AI nopes high-impact cards with some chance
    strong = ["Attack", "Favor", "Peek", "Shuffle", "See the Future", "Skip"]
    if any(s in card_name for s in strong):
        return random.random() < 0.7
    return random.random() < 0.03


def execute_card_effect(player, card):
    ss = st.session_state
    log(f"{player} plays {card}.")
    ss.discard_pile.append(card)

    if card == "Peek":
        target = "AI" if player == "Player" else "Player"
        peek_hand = ss.players[target][:3]
        if player == "Player":
            log(f"You peek at {target}'s first 3 cards: {peek_hand}")
        else:
            log(f"AI peeks at your cards.")
        return False

    if card == "Skip":
        log(f"{player}'s turn is skipped.")
        return True

    if card == "Attack":
        ss.attack_turns = ss.attack_turns + 1 if ss.attack_turns else 2
        log(f"Attack played: next player must take 2 turns.")
        return True

    if card == "See the Future":
        ss.seen_top_cards = ss.deck[:3]
        if player == "Player":
            log(f"THE FUTURE: {ss.seen_top_cards}")
        else:
            log("AI sees the top cards.")
        return False

    if card == "Favor":
        target = "AI" if player == "Player" else "Player"
        if ss.players[target]:
            if target == "AI":
                ai_hand_non_precious = [c for c in ss.players["AI"] if c not in ("Defuse", "Nope")]
                ai_gift = random.choice(ai_hand_non_precious) if ai_hand_non_precious else random.choice(ss.players["AI"])
                ss.players["AI"].remove(ai_gift)
                ss.players[player].append(ai_gift)
                log(f"AI gives {player} {ai_gift}.")
            else:
                # player gives a random card (for simplicity)
                gave = ss.players["Player"].pop(0)
                ss.players["AI"].append(gave)
                log(f"You gave AI {gave} (Favor fallback).")
        return False

    if card == "Shuffle":
        random.shuffle(ss.deck)
        log("Deck shuffled.")
        return False

    # cat cards, nope, defuse handled elsewhere
    return False


# ---------- High-level turns ----------

def player_play_card(card):
    ss = st.session_state
    if card not in ss.players["Player"]:
        log("Card not in hand.")
        return
    if card == "Defuse":
        log("Defuse can only be used when you draw an Exploding Kitten.")
        return

    # cat pair/trio should have separate UI
    if card == "Nope":
        log("Nope cannot be played proactively here.")
        return

    # set pending and check nope
    ss.players["Player"].remove(card)
    survives = try_nope_responses("Player", card)
    if not survives:
        log("Your play was NOPED.")
        # move card to discard (already removed)
        ss.discard_pile.append(card)
        ss.pending_action = None
        return
    # execute effect
    ended = execute_card_effect("Player", card)
    if ended:
        # skip drawing
        ss.turn = "AI"
        ss.player_ready_to_resolve = False
        ss.ai_pending = None
    else:
        ss.player_ready_to_resolve = False
        # after playing (if not skip/attack immediate), player must draw


def player_pair(cat):
    ss = st.session_state
    if ss.players["Player"].count(cat) < 2:
        log(f"You don't have two {cat}s.")
        return
    # remove two cats
    for _ in range(2):
        ss.players["Player"].remove(cat)
        ss.discard_pile.append(cat)
    # simple steal: pick random AI card
    if ss.players["AI"]:
        stolen = random.choice(ss.players["AI"])
        ss.players["AI"].remove(stolen)
        ss.players["Player"].append(stolen)
        log(f"You played a pair of {cat}s and stole {stolen} from AI.")
    else:
        log("AI has no cards to steal.")


def player_trio(cat, requested_card):
    ss = st.session_state
    if ss.players["Player"].count(cat) < 3:
        log(f"You don't have three {cat}s.")
        return
    for _ in range(3):
        ss.players["Player"].remove(cat)
        ss.discard_pile.append(cat)
    # ask for specific card
    found = None
    for c in ss.players["AI"]:
        if requested_card.lower() in c.lower():
            found = c
            break
    if found:
        ss.players["AI"].remove(found)
        ss.players["Player"].append(found)
        log(f"AI had {found}. You take it.")
    else:
        log("AI does not have that card.")


def ai_take_turn():
    ss = st.session_state
    if ss.game_over:
        return
    # simple AI heuristic: if danger (kitten in top 3 known), use skip/shuffle/attack
    top3 = ss.seen_top_cards if ss.seen_top_cards else ss.deck[:3]
    prob_kitten = "Exploding Kitten" in top3
    hand = ss.players["AI"]

    # prefer safety moves
    for danger in ("Skip", "Shuffle", "Attack"):
        if prob_kitten and danger in hand:
            hand.remove(danger)
            ss.discard_pile.append(danger)
            ss.pending_action = {"actor": "AI", "card": danger}
            # allow player to Nope; UI will show option to Nope AI
            ss.ai_pending = danger
            ss.player_ready_to_resolve = True
            log(f"AI intends to play {danger} (awaiting resolution).")
            return

    # see the future sometimes
    if "See the Future" in hand and not ss.seen_top_cards and random.random() < 0.6:
        hand.remove("See the Future")
        ss.discard_pile.append("See the Future")
        ss.seen_top_cards = ss.deck[:3]
        log(f"AI plays See the Future and views top cards.")
        ss.player_ready_to_resolve = False
        return

    # pair steal
    for cat in CAT_CARDS:
        if hand.count(cat) >= 2:
            for _ in range(2):
                hand.remove(cat)
                ss.discard_pile.append(cat)
            if ss.players["Player"]:
                # steal priority
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
                log(f"AI played a pair of {cat}s and stole {stolen}.")
                return

    # Favor
    if "Favor" in hand and (len(hand) < 8 or random.random() < 0.2):
        hand.remove("Favor")
        ss.discard_pile.append("Favor")
        if ss.players["Player"]:
            non_precious = [c for c in ss.players["Player"] if c not in ("Defuse", "Nope")]
            stolen = random.choice(non_precious) if non_precious else ss.players["Player"].pop(0)
            ss.players["Player"].remove(stolen)
            hand.append(stolen)
            log(f"AI played Favor and took your {stolen}.")
            return

    # Shuffle if deck low
    if "Shuffle" in hand and len(ss.deck) < 5:
        hand.remove("Shuffle")
        ss.discard_pile.append("Shuffle")
        random.shuffle(ss.deck)
        log("AI shuffled the deck.")
        return

    # otherwise draw
    draw_card("AI")


# ---------- Streamlit UI ----------

def main():
    st.set_page_config(page_title="Exploding Kittens — Streamlit", layout="wide")
    st.title("Exploding Kittens — Streamlit")

    if "deck" not in st.session_state:
        name = st.text_input("Enter your player name:", value="Player")
        if st.button("Start game"):
            init_game(name.strip() or "Player")
            st.experimental_rerun()
        st.stop()

    ss = st.session_state

    # left column: game actions
    col1, col2 = st.columns([2, 3])

    with col1:
        st.subheader("Your hand")
        st.write(sort_hand(ss.players["Player"]))

        st.subheader("Actions")
        if st.button("Draw"):
            draw_card("Player")
            # after drawing, if game not over, AI may take turn(s)
            if not ss.game_over:
                ss.turn = "AI"

        # play single card
        playable = [c for c in ss.players["Player"] if c not in ("Defuse", "Nope")]
        if playable:
            play_choice = st.selectbox("Play a card:", options=[""] + sorted(set(playable)))
            if play_choice:
                if st.button("Play selected card"):
                    player_play_card(play_choice)
                    # if player's turn ends, mark AI turn
                    if ss.turn == "AI":
                        pass
        else:
            st.info("No active playable cards (Defuse/Nope excluded).")

        # pair
        cats_with_two = [c for c in CAT_CARDS if ss.players["Player"].count(c) >= 2]
        if cats_with_two:
            pair_choice = st.selectbox("Play a pair of Cats:", options=[""] + cats_with_two, key="pair_choice")
            if pair_choice:
                if st.button("Play pair"):
                    player_pair(pair_choice)
        trio_with_three = [c for c in CAT_CARDS if ss.players["Player"].count(c) >= 3]
        if trio_with_three:
            trio_choice = st.selectbox("Play a trio of Cats:", options=[""] + trio_with_three, key="trio_choice")
            if trio_choice:
                req = st.text_input("If trio, request a specific card (partial name OK):", key="trio_req")
                if st.button("Play trio"):
                    player_trio(trio_choice, req.strip())

        # show decks and controls
        st.write(f"Deck: {len(ss.deck)} cards")
        st.write(f"Discard pile: {len(ss.discard_pile)} cards")

        if ss.player_ready_to_resolve and ss.pending_action:
            # show pending action details
            pa = ss.pending_action
            st.warning(f"Pending: {pa['actor']} -> {pa['card']}")
            if pa['actor'] == 'AI' and 'Nope' in ss.players['Player']:
                if st.button("Use Nope on AI"):
                    # player uses Nope to block AI
                    ss.players['Player'].remove('Nope')
                    ss.discard_pile.append('Nope')
                    log("You used Nope on AI's action. AI's action canceled.")
                    ss.pending_action = None
                    ss.player_ready_to_resolve = False
            if st.button("Resolve pending action"):
                # resolve pending action: if noped_by == AI then actor's action canceled
                if pa.get('noped_by') == 'AI':
                    log("AI's Nope canceled the action.")
                else:
                    # execute action now
                    execute_card_effect(pa['actor'], pa['card'])
                    # if actor was AI and action did not end its turn, let AI continue
                ss.pending_action = None
                ss.player_ready_to_resolve = False
                ss.ai_pending = None

    with col2:
        st.subheader("Game log")
        for entry in ss.history[-30:]:
            st.write(entry)

        st.subheader("AI hand (hidden) / Your status")
        st.write(f"AI has {len(ss.players['AI'])} cards.")
        st.write(f"Your Defuse count: {ss.players['Player'].count('Defuse')}")
        st.write(f"Your Nope count: {ss.players['Player'].count('Nope')}")

        # AI turn resolution
        if ss.turn == "AI" and not ss.game_over and not ss.player_ready_to_resolve:
            if st.button("Let AI play now"):
                ai_take_turn()
                # if AI set a pending_action (e.g., played something that player can Nope), don't auto-resolve
                if not ss.player_ready_to_resolve:
                    # if AI didn't set player-ready, after AI actions, switch back to player
                    ss.turn = "Player"
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
            if st.button("Restart"): 
                init_game(ss.player_name)
                st.experimental_rerun()

    # Footer controls
    st.markdown("---")
    st.write("Controls: Draw to draw a card. Play cards, pairs or trios. When AI is about to play certain cards you may be offered a chance to use 'Nope'.")
    st.write("To fully automate turns, press 'Let AI play now' on AI's turn.")


if __name__ == '__main__':
    # ensure session state keys exist
    if 'deck' not in st.session_state:
        st.session_state.clear()
    main()
