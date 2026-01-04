import streamlit as st
import random
import json
import os
import time

# --- PROFESSIONAL STYLING (THE "PRO" LOOK) ---
st.set_page_config(page_title="Exploding Kittens | Pro Edition", layout="wide")

st.markdown("""
    <style>
    /* Main Background */
    .stApp {
        background-color: #0E1117;
        color: #E0E0E0;
    }
    
    /* Card Component */
    .card-pro {
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 15px;
        background-color: #161B22;
        text-align: center;
        transition: transform 0.2s;
        min-height: 120px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .card-pro:hover {
        border-color: #58A6FF;
    }
    .card-title {
        color: #58A6FF;
        font-weight: 600;
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Stats Sidebar */
    .css-163ttbj {
        background-color: #010409;
    }
    
    /* Custom Button Styling */
    div.stButton > button:first-child {
        background-color: #21262D;
        color: #C9D1D9;
        border: 1px solid #30363D;
        border-radius: 6px;
        width: 100%;
    }
    div.stButton > button:hover {
        border-color: #8B949E;
        color: #FFFFFF;
    }
    </style>
""", unsafe_allow_html=True)

# --- GAME CONSTANTS ---
CARD_TYPES = {
    "Exploding Kitten": 1, "Defuse": 3, "Nope": 6, "Taco Cat": 7,
    "Beard Cat": 7, "Rainbow Ralphing Cat": 7, "Skip": 4, "Attack": 4,
    "See the Future": 4, "Favor": 3, "Shuffle": 3, "Peek": 1, "Unlucky": 2,
}
CAT_CARDS = ["Taco Cat", "Beard Cat", "Rainbow Ralphing Cat"]

# --- SESSION STATE INITIALIZATION ---
if 'init' not in st.session_state:
    st.session_state.init = True
    st.session_state.p_hand = []
    st.session_state.ai_hand = []
    st.session_state.deck = []
    st.session_state.discard = []
    st.session_state.turn = "Player"
    st.session_state.attack_turns = 0
    st.session_state.game_over = False
    st.session_state.winner = None
    st.session_state.logs = []
    st.session_state.history = []
    st.session_state.phase = "MAIN" # MAIN, NOPE_OPPORTUNITY, DISCARD_REQUIRED, FAVOR_WAIT
    st.session_state.pending_action = None # Card being played

# --- CORE LOGIC FUNCTIONS ---
def log_event(msg):
    st.session_state.logs.insert(0, msg)
    st.session_state.history.append(msg)

def save_stats(winner):
    stats_file = "ek_stats.json"
    data = {"games_played": 0, "player_wins": 0, "ai_wins": 0}
    if os.path.exists(stats_file):
        with open(stats_file, "r") as f: data = json.load(f)
    data["games_played"] += 1
    if winner == "Player": data["player_wins"] += 1
    else: data["ai_wins"] += 1
    with open(stats_file, "w") as f: json.dump(data, f)

def setup_game():
    temp_deck = []
    for card, count in CARD_TYPES.items():
        if card not in ["Exploding Kitten", "Defuse"]:
            temp_deck.extend([card] * count)
    random.shuffle(temp_deck)
    
    st.session_state.p_hand = [temp_deck.pop() for _ in range(4)] + ["Defuse"]
    st.session_state.ai_hand = [temp_deck.pop() for _ in range(4)] + ["Defuse"]
    
    st.session_state.deck = temp_deck + ["Exploding Kitten"]
    random.shuffle(st.session_state.deck)
    st.session_state.game_over = False
    st.session_state.phase = "MAIN"
    log_event("DECK INITIALIZED: SYSTEM READY")

def process_draw(player):
    if not st.session_state.deck:
        log_event("DECK EMPTY: RECYCLING DISCARD PILE")
        st.session_state.deck = st.session_state.discard[:]
        st.session_state.discard = []
        random.shuffle(st.session_state.deck)
    
    card = st.session_state.deck.pop(0)
    
    if card == "Exploding Kitten":
        if "Defuse" in st.session_state[f"{'p' if player=='Player' else 'ai'}_hand"]:
            st.session_state[f"{'p' if player=='Player' else 'ai'}_hand"].remove("Defuse")
            st.session_state.discard.append("Defuse")
            # Logic: insert kitten at random index
            idx = random.randint(0, len(st.session_state.deck))
            st.session_state.deck.insert(idx, "Exploding Kitten")
            log_event(f"ALERT: {player.upper()} DEFUSED EXPLODING KITTEN")
        else:
            st.session_state.game_over = True
            st.session_state.winner = "AI" if player == "Player" else "Player"
            save_stats(st.session_state.winner)
            log_event(f"CRITICAL: {player.upper()} EXPLODED")
            return
            
    elif card == "Unlucky":
        log_event(f"UNLUCKY: {player.upper()} MUST DISCARD")
        if player == "Player":
            st.session_state.phase = "DISCARD_REQUIRED"
        else:
            if st.session_state.ai_hand:
                c = random.choice(st.session_state.ai_hand)
                st.session_state.ai_hand.remove(c)
                st.session_state.discard.append(c)
    else:
        st.session_state[f"{'p' if player=='Player' else 'ai'}_hand"].append(card)
        log_event(f"DRAW: {player.upper()} RECEIVED {card.upper()}")

    # Turn switching logic for simple draws
    if st.session_state.phase == "MAIN":
        if st.session_state.attack_turns > 0:
            st.session_state.attack_turns -= 1
            if st.session_state.attack_turns == 0:
                st.session_state.turn = "AI" if player == "Player" else "Player"
        else:
            st.session_state.turn = "AI" if player == "Player" else "Player"

def execute_card(card, player):
    st.session_state.discard.append(card)
    log_event(f"ACTION: {player.upper()} PLAYED {card.upper()}")
    
    if card == "Skip":
        st.session_state.turn = "AI" if player == "Player" else "Player"
    elif card == "Attack":
        st.session_state.attack_turns = 2
        st.session_state.turn = "AI" if player == "Player" else "Player"
    elif card == "See the Future":
        st.session_state.future = st.session_state.deck[:3]
        log_event(f"FUTURE DATA: {', '.join(st.session_state.future)}")
    elif card == "Shuffle":
        random.shuffle(st.session_state.deck)
        log_event("SYSTEM: DECK SHUFFLED")
    elif card == "Favor":
        st.session_state.phase = "FAVOR_WAIT"
    elif card == "Peek":
        target = st.session_state.ai_hand if player == "Player" else st.session_state.p_hand
        log_event(f"PEEK DATA: {target[:2]}")

# --- SIDEBAR: STATS & LOGS ---
with st.sidebar:
    st.title("COMMAND CENTER")
    if os.path.exists("ek_stats.json"):
        with open("ek_stats.json", "r") as f:
            stats = json.load(f)
            st.metric("GAMES PLAYED", stats["games_played"])
            st.metric("PLAYER WINS", stats["player_wins"])
            st.metric("AI WINS", stats["ai_wins"])
    
    st.divider()
    st.subheader("ACTIVITY LOG")
    for log in st.session_state.logs[:15]:
        st.caption(log)

# --- MAIN UI ---
if not st.session_state.p_hand and not st.session_state.game_over:
    st.header("SURVIVAL INTERFACE")
    if st.button("INITIALIZE SESSION"):
        setup_game()
        st.rerun()

elif st.session_state.game_over:
    st.title("SESSION TERMINATED")
    st.header(f"WINNER: {st.session_state.winner.upper()}")
    if st.button("RESTART SYSTEM"):
        setup_game()
        st.rerun()
    
    st.divider()
    st.subheader("REPLAY DATA")
    st.write(st.session_state.history)

else:
    # Top Row: AI Status & Deck
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        st.write("OPPONENT: AI")
        st.code(f"CARDS: {len(st.session_state.ai_hand)}")
    with c2:
        st.markdown(f"<div style='text-align:center'><h3>SYSTEM PHASE: {st.session_state.turn.upper()}</h3></div>", unsafe_allow_html=True)
        if st.session_state.discard:
            st.markdown(f"""
                <div style="background-color: #010409; padding: 20px; border: 1px solid #30363D; text-align: center; border-radius: 10px;">
                    <p style="color: #8B949E; font-size: 0.8rem;">DISCARD STACK TOP</p>
                    <h2 style="color: #E6EDF3;">{st.session_state.discard[-1].upper()}</h2>
                </div>
            """, unsafe_allow_html=True)
    with c3:
        st.write("DECK STATUS")
        st.code(f"REMAINING: {len(st.session_state.deck)}")

    st.divider()

    # Interaction Phase
    if st.session_state.phase == "DISCARD_REQUIRED":
        st.warning("UNLUCKY PROTOCOL: SELECT A CARD TO DISCARD")
        cols = st.columns(len(st.session_state.p_hand))
        for i, card in enumerate(st.session_state.p_hand):
            if cols[i].button(card, key=f"disc_{i}"):
                st.session_state.p_hand.remove(card)
                st.session_state.discard.append(card)
                st.session_state.phase = "MAIN"
                st.rerun()

    elif st.session_state.phase == "FAVOR_WAIT":
        st.info("FAVOR PROTOCOL: WAITING FOR TRANSACTION")
        if st.session_state.turn == "Player":
            # AI gives to player
            if st.session_state.ai_hand:
                gift = random.choice(st.session_state.ai_hand)
                st.session_state.ai_hand.remove(gift)
                st.session_state.p_hand.append(gift)
                log_event(f"TRANSFER: RECEIVED {gift.upper()} FROM AI")
            st.session_state.phase = "MAIN"
            st.rerun()

    elif st.session_state.turn == "Player":
        col_draw, col_help = st.columns([1, 1])
        if col_draw.button("DRAW CARD / END TURN", type="primary"):
            process_draw("Player")
            st.rerun()
        
        st.subheader("PLAYER HAND")
        # Grid of cards
        cols = st.columns(5)
        for i, card in enumerate(st.session_state.p_hand):
            with cols[i % 5]:
                st.markdown(f"""
                    <div class="card-pro">
                        <div class="card-title">{card}</div>
                    </div>
                """, unsafe_allow_html=True)
                
                # Logic for playing
                if card in ["Defuse", "Nope", "Exploding Kitten"]:
                    st.button("LOCKED", key=f"btn_{i}", disabled=True)
                else:
                    if st.button("EXECUTE", key=f"btn_{i}"):
                        st.session_state.p_hand.remove(card)
                        execute_card(card, "Player")
                        st.rerun()
        
        # Pairs / Trios Section
        st.divider()
        st.subheader("COMBINATORIAL ACTIONS")
        cat_counts = {cat: st.session_state.p_hand.count(cat) for cat in CAT_CARDS}
        pc1, pc2 = st.columns(2)
        for cat, count in cat_counts.items():
            if count >= 2:
                if pc1.button(f"PAIR: {cat.upper()}"):
                    for _ in range(2): st.session_state.p_hand.remove(cat)
                    # Steal random from AI
                    if st.session_state.ai_hand:
                        stolen = random.choice(st.session_state.ai_hand)
                        st.session_state.ai_hand.remove(stolen)
                        st.session_state.p_hand.append(stolen)
                        log_event(f"THEFT: ACQUIRED {stolen.upper()}")
                    st.rerun()
            if count >= 3:
                if pc2.button(f"TRIO: {cat.upper()}"):
                    # Simplified Trio for Streamlit: asks for random valuable card
                    for _ in range(3): st.session_state.p_hand.remove(cat)
                    target = "Defuse"
                    if target in st.session_state.ai_hand:
                        st.session_state.ai_hand.remove(target)
                        st.session_state.p_hand.append(target)
                        log_event(f"TRIO SUCCESS: ACQUIRED {target.upper()}")
                    else:
                        log_event("TRIO FAILURE: AI DOES NOT HAVE TARGET")
                    st.rerun()

    else:
        # AI TURN
        st.info("AI PROCESSING...")
        time.sleep(1.5)
        # AI Simple logic: play a card if it has one, otherwise draw
        playable = [c for c in st.session_state.ai_hand if c not in ["Defuse", "Nope"] + CAT_CARDS]
        if playable and random.random() > 0.5:
            c = playable[0]
            st.session_state.ai_hand.remove(c)
            execute_card(c, "AI")
        else:
            process_draw("AI")
        st.rerun()
