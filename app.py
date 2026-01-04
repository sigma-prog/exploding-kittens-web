import streamlit as st
import random
import json
import os
import time

# --- CONSTANTS ---
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
STATS_FILE = "ek_stats.json"

def sort_hand(hand):
    order = ['Defuse', 'Nope', 'Skip', 'Attack', 'See the Future', 'Favor', 'Shuffle', 'Peek', 'Unlucky', 'Taco Cat', 'Beard Cat', 'Rainbow Ralphing Cat']
    return sorted(hand, key=lambda c: order.index(c) if c in order else 99)

# --- STATS PERSISTENCE ---
def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r") as f: return json.load(f)
        except: pass
    return {"games_played": 0, "player_wins": 0, "ai_wins": 0}

def save_stats(stats):
    with open(STATS_FILE, "w") as f: json.dump(stats, f)

# --- SESSION INITIALIZATION ---
if 'game_initialized' not in st.session_state:
    st.session_state.deck = []
    st.session_state.discard_pile = []
    st.session_state.player_hand = []
    st.session_state.ai_hand = []
    st.session_state.log = []
    st.session_state.history = []
    st.session_state.game_over = False
    st.session_state.winner = None
    st.session_state.attack_turns = 0
    st.session_state.turn = "Player"
    st.session_state.seen_top_cards = []
    st.session_state.pending_action = None 
    st.session_state.nope_chain_active = False
    st.session_state.last_played_card = None
    st.session_state.action_blocked = False
    st.session_state.game_initialized = True
    
    # Setup Deck
    temp_deck = []
    for card, count in CARD_TYPES.items():
        if card not in ["Exploding Kitten", "Defuse"]:
            temp_deck.extend([card] * count)
    random.shuffle(temp_deck)
    
    # Deal
    st.session_state.player_hand = [temp_deck.pop() for _ in range(4)] + ["Defuse"]
    st.session_state.ai_hand = [temp_deck.pop() for _ in range(4)] + ["Defuse"]
    st.session_state.player_hand = sort_hand(st.session_state.player_hand)
    
    st.session_state.deck = temp_deck + ["Exploding Kitten"]
    random.shuffle(st.session_state.deck)
    st.session_state.log.append("Game Started. Stats loaded.")

def add_log(msg, player="System"):
    entry = f"[{player}] {msg}"
    st.session_state.log.append(entry)
    st.session_state.history.append({"player": player, "msg": msg})

# --- GAME LOGIC ---

def draw_card(player_name):
    if not st.session_state.deck:
        if not st.session_state.discard_pile:
            st.session_state.game_over = True
            st.session_state.winner = "AI" if player_name == "Player" else "Player"
            return
        add_log("Deck empty. Shuffling discard pile back in.")
        st.session_state.deck = st.session_state.discard_pile[:]
        st.session_state.discard_pile = []
        random.shuffle(st.session_state.deck)

    card = st.session_state.deck.pop(0)
    
    if card == "Unlucky":
        add_log(f"drew Unlucky! A random card was lost.", player_name)
        hand = st.session_state.player_hand if player_name == "Player" else st.session_state.ai_hand
        if hand:
            lost = random.choice(hand)
            hand.remove(lost)
            st.session_state.discard_pile.append(lost)
        return True

    if card == "Exploding Kitten":
        hand = st.session_state.player_hand if player_name == "Player" else st.session_state.ai_hand
        if "Defuse" in hand:
            hand.remove("Defuse")
            st.session_state.discard_pile.append("Defuse")
            idx = random.randint(0, len(st.session_state.deck))
            st.session_state.deck.insert(idx, "Exploding Kitten")
            add_log(f"used Defuse! Kitten returned to deck at random position.", player_name)
            st.session_state.seen_top_cards = []
        else:
            st.session_state.game_over = True
            st.session_state.winner = "AI" if player_name == "Player" else "Player"
            add_log(f"exploded! Game Over.", player_name)
            # Update Stats
            stats = load_stats()
            stats["games_played"] += 1
            if st.session_state.winner == "Player": stats["player_wins"] += 1
            else: stats["ai_wins"] += 1
            save_stats(stats)
    else:
        if player_name == "Player":
            st.session_state.player_hand.append(card)
            st.session_state.player_hand = sort_hand(st.session_state.player_hand)
        else:
            st.session_state.ai_hand.append(card)
        add_log(f"drew safely.", player_name)

def execute_effect(card, player):
    if st.session_state.action_blocked:
        add_log(f"{card} was blocked by a Nope!", player)
        st.session_state.action_blocked = False
        return

    add_log(f"played {card}", player)
    if card == "Skip": end_turn()
    elif card == "Attack": 
        st.session_state.attack_turns = 2
        end_turn()
    elif card == "See the Future": st.session_state.seen_top_cards = st.session_state.deck[:3]
    elif card == "Shuffle": random.shuffle(st.session_state.deck)
    elif card == "Peek": 
        target = "AI" if player == "Player" else "Player"
        t_hand = st.session_state.ai_hand if target == "AI" else st.session_state.player_hand
        add_log(f"Peeked at {target}'s hand: {t_hand[:2]}", player)
    elif card == "Favor": 
        st.session_state.pending_action = {"type": "favor", "source": player}

def end_turn():
    if st.session_state.attack_turns > 0:
        st.session_state.attack_turns -= 1
        add_log(f"Attack active. Extra turn remaining for {st.session_state.turn}.")
    else:
        st.session_state.turn = "AI" if st.session_state.turn == "Player" else "Player"
        if st.session_state.turn == "AI":
            run_ai_logic()

def run_ai_logic():
    hand = st.session_state.ai_hand
    # AI checks for danger
    top_cards = st.session_state.seen_top_cards if st.session_state.seen_top_cards else st.session_state.deck[:3]
    
    # AI plays defensive if kitten is near
    if "Exploding Kitten" in top_cards:
        for escape in ["Skip", "Shuffle", "Attack"]:
            if escape in hand:
                # AI plays card
                hand.remove(escape)
                st.session_state.discard_pile.append(escape)
                # Check for player Nope (Simplified for AI turn flow)
                execute_effect(escape, "AI")
                return

    # Draw if no defensive moves needed
    draw_card("AI")
    st.session_state.turn = "Player"

# --- UI SETUP ---
st.set_page_config(page_title="Exploding Kittens Full", layout="wide")
st.title("Exploding Kittens")

stats = load_stats()
st.sidebar.subheader("Lifetime Stats")
st.sidebar.write(f"Games: {stats['games_played']}")
st.sidebar.write(f"Your Wins: {stats['player_wins']}")
st.sidebar.write(f"AI Wins: {stats['ai_wins']}")

if st.session_state.game_over:
    st.header(f"Final Result: {st.session_state.winner} Wins!")
    
    with st.expander("Show Game History Replay"):
        for i, entry in enumerate(st.session_state.history):
            st.write(f"{i+1}. {entry['player']}: {entry['msg']}")
            
    if st.button("Play Again"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
else:
    # --- NOPE OVERLAY ---
    if st.session_state.nope_chain_active:
        st.warning(f"WAIT! {st.session_state.last_played_card} was played. Do you want to NOPE it?")
        c1, c2 = st.columns(2)
        if "Nope" in st.session_state.player_hand:
            if c1.button("PLAY NOPE"):
                st.session_state.player_hand.remove("Nope")
                st.session_state.discard_pile.append("Nope")
                st.session_state.action_blocked = not st.session_state.action_blocked
                add_log("played NOPE!", "Player")
                # AI Logic: AI tries to Nope back
                if "Nope" in st.session_state.ai_hand and random.random() < 0.5:
                    st.session_state.ai_hand.remove("Nope")
                    st.session_state.discard_pile.append("Nope")
                    st.session_state.action_blocked = not st.session_state.action_blocked
                    add_log("played NOPE back!", "AI")
                st.rerun()
        if c2.button("PASS (Let it happen)"):
            st.session_state.nope_chain_active = False
            execute_effect(st.session_state.last_played_card, "Player")
            st.rerun()
        st.stop()

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Your Hand")
        cols = st.columns(4)
        for i, card in enumerate(st.session_state.player_hand):
            with cols[i % 4]:
                if st.button(card, key=f"c_{i}", use_container_width=True):
                    if card == "Defuse": st.error("Defuse is automatic.")
                    elif card == "Nope": st.info("Use Nope when the AI plays a card.")
                    elif card in CAT_CARDS:
                        st.session_state.pending_action = {"type": "cat_check", "card": card}
                        st.rerun()
                    else:
                        st.session_state.player_hand.remove(card)
                        st.session_state.discard_pile.append(card)
                        st.session_state.last_played_card = card
                        # Check if AI wants to Nope you
                        if "Nope" in st.session_state.ai_hand and random.random() < 0.3:
                            st.session_state.ai_hand.remove("Nope")
                            st.session_state.discard_pile.append("Nope")
                            add_log("AI used NOPE on your turn!", "AI")
                            st.session_state.action_blocked = True
                        
                        # In the web version, we use the overlay for player Nopes, 
                        # but for regular cards we execute immediately unless blocked
                        execute_effect(card, "Player")
                        st.rerun()

        st.divider()
        if st.button("Draw Card & End Turn", type="primary", use_container_width=True):
            draw_card("Player")
            if not st.session_state.game_over: end_turn()
            st.rerun()

    with col2:
        st.subheader("Table")
        st.write(f"Deck: {len(st.session_state.deck)} | Discard: {len(st.session_state.discard_pile)}")
        if st.session_state.seen_top_cards:
            st.info(f"Future: {st.session_state.seen_top_cards}")
        
        # Action Center
        if st.session_state.pending_action:
            act = st.session_state.pending_action
            st.write("--- Action Required ---")
            
            if act["type"] == "cat_check":
                card_name = act["card"]
                count = st.session_state.player_hand.count(card_name)
                st.write(f"You have {count} {card_name}s.")
                if count >= 2 and st.button("Play Pair (Steal Random)"):
                    for _ in range(2): st.session_state.player_hand.remove(card_name)
                    st.session_state.pending_action = {"type": "steal"}
                    st.rerun()
                if count >= 3 and st.button("Play Trio (Ask for Card)"):
                    for _ in range(3): st.session_state.player_hand.remove(card_name)
                    st.session_state.pending_action = {"type": "ask"}
                    st.rerun()
                if st.button("Cancel"):
                    st.session_state.pending_action = None
                    st.rerun()

            elif act["type"] == "ask":
                target_card = st.selectbox("Ask AI for:", list(CARD_TYPES.keys()))
                if st.button("Confirm Ask"):
                    if target_card in st.session_state.ai_hand:
                        st.session_state.ai_hand.remove(target_card)
                        st.session_state.player_hand.append(target_card)
                        add_log(f"asked for {target_card} and AI HAD IT!", "Player")
                    else:
                        add_log(f"asked for {target_card} but AI didn't have it.", "Player")
                    st.session_state.pending_action = None
                    st.rerun()

            elif act["type"] == "steal":
                if st.button("Pull Card from AI"):
                    if st.session_state.ai_hand:
                        stolen = st.session_state.ai_hand.pop(random.randint(0, len(st.session_state.ai_hand)-1))
                        st.session_state.player_hand.append(stolen)
                        add_log(f"stole {stolen} from AI.", "Player")
                    st.session_state.pending_action = None
                    st.rerun()

            elif act["type"] == "favor":
                if st.button("Get card from AI"):
                    if st.session_state.ai_hand:
                        gift = st.session_state.ai_hand.pop(random.randint(0, len(st.session_state.ai_hand)-1))
                        st.session_state.player_hand.append(gift)
                        add_log(f"received {gift} via Favor.", "Player")
                    st.session_state.pending_action = None
                    st.rerun()

        st.subheader("Activity Log")
        for m in reversed(st.session_state.log[-12:]):
            st.text(m)

st.markdown("<style>.stButton>button { border-radius: 4px; font-weight: bold; }</style>", unsafe_allow_html=True)