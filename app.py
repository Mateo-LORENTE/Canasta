import streamlit as st
import json
import os
import math
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import base64
from datetime import datetime, timezone, timedelta


def now_fr():
    return datetime.now(timezone.utc) + timedelta(hours=2)
# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
PASSWORD = "canasta2024"   # Change ici ton mot de passe
K = 30

GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
GITHUB_REPO  = st.secrets["GITHUB_REPO"]
GITHUB_FILE  = st.secrets["GITHUB_FILE"]
GITHUB_API   = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
HEADERS      = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

st.set_page_config(page_title="Classement Canasta", page_icon="🃏", layout="wide")

# ─────────────────────────────────────────
# GITHUB STORAGE
# ─────────────────────────────────────────
def load_data():
    try:
        r = requests.get(GITHUB_API, headers=HEADERS)
        if r.status_code == 200:
            content = base64.b64decode(r.json()["content"]).decode("utf-8")
            data = json.loads(content)
            st.session_state["github_sha"] = r.json()["sha"]
            return data
        else:
            return {"players": {}, "history": [], "elo_history": {}}
    except Exception as e:
        st.error(f"Erreur chargement données : {e}")
        return {"players": {}, "history": [], "elo_history": {}}

def save_data(data):
    try:
        content = base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")).decode("utf-8")
        payload = {
            "message": f"update data {now_fr().strftime('%d/%m/%Y %H:%M')}",
            "content": content,
        }
        if "github_sha" in st.session_state:
            payload["sha"] = st.session_state["github_sha"]
        r = requests.put(GITHUB_API, headers=HEADERS, json=payload)
        if r.status_code in [200, 201]:
            st.session_state["github_sha"] = r.json()["content"]["sha"]
        else:
            st.error(f"Erreur sauvegarde : {r.json()}")
    except Exception as e:
        st.error(f"Erreur sauvegarde : {e}")

# ─────────────────────────────────────────
# MOT DE PASSE
# ─────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🃏 Classement Canasta")
    pwd = st.text_input("Mot de passe", type="password")
    if st.button("Entrer"):
        if pwd == PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Mot de passe incorrect.")
    st.stop()

# ─────────────────────────────────────────
# CHARGEMENT DONNÉES
# ─────────────────────────────────────────
if "data" not in st.session_state:
    st.session_state.data = load_data()

data        = st.session_state.data
players     = data["players"]
history     = data["history"]
elo_history = data.get("elo_history", {})

# ─────────────────────────────────────────
# ELO
# ─────────────────────────────────────────
def expected_score(rA, rB):
    return 1 / (1 + 10 ** ((rB - rA) / 400))

def expected_score_3(rA, rB, rC):
    return 1 / (1 + 10 ** (((rB + rC) / 2 - rA) / 400))

def avg_elo(names):
    return sum(players[n] for n in names) / len(names)

def update_elo(winners, losers, neutrals):
    snapshot = {n: players[n] for n in winners + losers + neutrals}

    if neutrals:
        avg_win = avg_elo(winners)
        avg_neu = avg_elo(neutrals)
        avg_los = avg_elo(losers)
        exp_win = expected_score_3(avg_win, avg_neu, avg_los)
        exp_neu = expected_score_3(avg_neu, avg_neu, avg_win)
        exp_los = expected_score_3(avg_los, avg_win, avg_los)
        for p in winners:  players[p] += K * (1   - exp_win)
        for p in neutrals: players[p] += K * (0.5 - exp_neu)
        for p in losers:   players[p] += K * (0   - exp_los)
    else:
        avg_win = avg_elo(winners)
        avg_los = avg_elo(losers)
        exp_win = expected_score(avg_win, avg_los)
        exp_los = expected_score(avg_los, avg_win)
        for p in winners: players[p] += K * (1 - exp_win)
        for p in losers:  players[p] += K * (0 - exp_los)

    for p in winners + losers + neutrals:
        players[p] = round(players[p])

    deltas = {n: players[n] - snapshot[n] for n in snapshot}

    entry = {
        "date": now_fr().strftime("%d/%m/%Y %H:%M"),
        "winners": winners,
        "losers": losers,
        "neutrals": neutrals,
        "deltas": deltas,
        "snapshot_before": snapshot,
    }
    history.insert(0, entry)

    ts = now_fr().strftime("%d/%m/%Y %H:%M")
    for p in winners + losers + neutrals:
        if p not in elo_history:
            elo_history[p] = []
        elo_history[p].append({"date": ts, "elo": players[p]})

    data["elo_history"] = elo_history
    save_data(data)

# ─────────────────────────────────────────
# NAVIGATION
# ─────────────────────────────────────────
st.sidebar.title("🃏 Canasta")
page = st.sidebar.radio("Navigation", ["🏆 Classement", "⚔️ Match", "📈 Statistiques", "👤 Joueurs"])
st.sidebar.markdown("---")
if st.sidebar.button("🔄 Rafraîchir les données"):
    del st.session_state["data"]
    st.rerun()
if st.sidebar.button("🔒 Se déconnecter"):
    st.session_state.authenticated = False
    st.rerun()

# ─────────────────────────────────────────
# PAGE : CLASSEMENT
# ─────────────────────────────────────────
if page == "🏆 Classement":
    st.title("🏆 Classement")

    if not players:
        st.info("Aucun joueur pour l'instant. Ajoutez des joueurs dans l'onglet Joueurs.")
    else:
        sorted_players = sorted(players.items(), key=lambda x: x[1], reverse=True)

        medals = ["🥇", "🥈", "🥉"]

        for i, (name, elo) in enumerate(sorted_players):
            rank = medals[i] if i < 3 else str(i + 1)
            played  = sum(1 for m in history if name in m["winners"] + m["losers"] + m.get("neutrals", []))
            wins    = sum(1 for m in history if name in m["winners"])
            winrate = f"{round(wins/played*100)}%" if played > 0 else "—"
        
            with st.container():
                st.markdown(f"""
                <div style="display:flex; justify-content:space-between; align-items:center;
                            padding:10px 8px; border-bottom:1px solid #333;">
                    <span style="font-size:18px;">{rank} <strong>{name}</strong></span>
                    <span style="font-size:13px; color:gray;">{played} matchs · {winrate}</span>
                    <span style="font-size:16px; font-weight:bold;">{elo}</span>
                </div>
                """, unsafe_allow_html=True)


        st.markdown("")
        st.markdown("")
        def get_streaks(name):
            win_streak  = 0
            lose_streak = 0
        
            for m in history:  # history est déjà du plus récent au plus ancien
                all_p = m["winners"] + m["losers"] + m.get("neutrals", [])
                if name not in all_p:
                    continue
                delta = m["deltas"].get(name, 0)
                if delta == 0:
                    continue
                if delta > 0:
                    win_streak += 1
                else:
                    break
        
            for m in history:
                all_p = m["winners"] + m["losers"] + m.get("neutrals", [])
                if name not in all_p:
                    continue
                delta = m["deltas"].get(name, 0)
                if delta == 0:
                    continue
                if delta < 0:
                    lose_streak += 1
                else:
                    break
        
            return win_streak, lose_streak
        
        if history:
            best_win  = max(players.keys(), key=lambda n: get_streaks(n)[0])
            best_lose = max(players.keys(), key=lambda n: get_streaks(n)[1])
        
            win_streak  = get_streaks(best_win)[0]
            lose_streak = get_streaks(best_lose)[1]
        
            if win_streak > 0:
                st.markdown(f"""
            <div style="background-color:rgba(200,0,0,0.15); border:1px solid rgba(200,0,0,0.4); padding:8px; border-radius:10px;">
                🔥 <strong>Joueur à abattre : {best_win}</strong><br><br>
                {win_streak} victoires consécutives
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("")
            
            if lose_streak > 0:
                st.markdown(f"""
            <div style="background-color:rgba(0,80,200,0.15); border:1px solid rgba(0,80,200,0.4); padding:8px; border-radius:10px;">
                🤡 <strong>Neuil du moment : {best_lose}</strong><br><br>
                {lose_streak} défaites consécutives
            </div>
            """, unsafe_allow_html=True)
# ─────────────────────────────────────────
# PAGE : MATCH
# ─────────────────────────────────────────
elif page == "⚔️ Match":
  
        
    st.title("⚔️ Enregistrer un match")

    if len(players) < 2:
        st.warning("Il faut au moins 2 joueurs pour enregistrer un match.")
    else:
        all_names = list(players.keys())

        winners  = st.multiselect("🏆 Gagnants",  all_names, key="w")
        losers   = st.multiselect("💀 Perdants",  all_names, key="l")
        neutrals = st.multiselect("😐 Neutres (optionnel)", all_names, key="n")

        all_selected = winners + losers + neutrals
        overlap = len(all_selected) != len(set(all_selected))

        if winners and losers:
            if overlap:
                st.error("Un joueur ne peut pas être dans deux catégories à la fois.")
            else:
                st.markdown("### Aperçu des changements")

                def sim_elo(w, l, n):
                    def avg(names): return sum(players[x] for x in names) / len(names)
                    if n:
                        aw, an, al = avg(w), avg(n), avg(l)
                        ew = expected_score_3(aw, an, al)
                        en = expected_score_3(an, an, aw)
                        el = expected_score_3(al, aw, al)
                        d = {}
                        for p in w: d[p] = round(K * (1   - ew))
                        for p in n: d[p] = round(K * (0.5 - en))
                        for p in l: d[p] = round(K * (0   - el))
                    else:
                        aw, al = avg(w), avg(l)
                        ew = expected_score(aw, al)
                        el = expected_score(al, aw)
                        d = {}
                        for p in w: d[p] = round(K * (1 - ew))
                        for p in l: d[p] = round(K * (0 - el))
                    return d

                preview = sim_elo(winners, losers, neutrals)
                preview_cols = st.columns(len(all_selected))
                for i, name in enumerate(all_selected):
                    delta = preview.get(name, 0)
                    sign  = "+" if delta >= 0 else ""
                    preview_cols[i].metric(name, players[name], f"{sign}{delta}")

                st.markdown("")
                if st.button("✅ Valider le match", type="primary"):
                    update_elo(winners, losers, neutrals)
                    for key in ["w", "l", "n"]:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.success("Match enregistré !")
                    st.rerun()

        if history:
            st.markdown("---")
            st.markdown("### Derniers matchs")
            for m in history[:10]:
                w = ", ".join(m["winners"])
                l = ", ".join(m["losers"])
                n = f" | Neutres: {', '.join(m['neutrals'])}" if m.get("neutrals") else ""
                st.markdown(f"**{m['date']}** — 🏆 {w} vs 💀 {l}{n}")
                detail = " | ".join(
                    f"{p}: {'+'if m['deltas'][p]>=0 else ''}{m['deltas'][p]}"
                    for p in m["deltas"]
                )
                st.caption(detail)

# ─────────────────────────────────────────
# PAGE : STATISTIQUES
# ─────────────────────────────────────────
elif page == "📈 Statistiques":
    st.title("📈 Statistiques")

    if not players:
        st.info("Aucun joueur.")
    else:
        total_matchs = len(history)
        st.metric("Matchs joués", total_matchs)

        if history:
            st.markdown("---")

            # Tableau stats par joueur
            stats = []
            for name in players:
                played  = sum(1 for m in history if name in m["winners"] + m["losers"] + m.get("neutrals", []))
                wins    = sum(1 for m in history if name in m["winners"])
                losses  = sum(1 for m in history if name in m["losers"])
                neutral = sum(1 for m in history if name in m.get("neutrals", []))
                winrate = round(wins / played * 100) if played > 0 else 0
                stats.append({
                    "Joueur": name,
                    "Elo": players[name],
                    "Matchs": played,
                    "Victoires": wins,
                    "Défaites": losses,
                    "Neutres": neutral,
                    "Win rate (%)": winrate,
                })

            df_stats = pd.DataFrame(stats).sort_values("Elo", ascending=False).reset_index(drop=True)
            st.dataframe(df_stats, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("### Évolution de l'Elo")
            selected = st.multiselect("Joueurs à afficher", list(players.keys()), default=list(players.keys()))

            if selected and elo_history:
                fig = go.Figure()
                for name in selected:
                    if name in elo_history and elo_history[name]:
                        h = elo_history[name]
                        fig.add_trace(go.Scatter(
                            x=[e["date"] for e in h],
                            y=[e["elo"]  for e in h],
                            mode="lines+markers",
                            name=name,
                        ))
                fig.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Elo",
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Jouez des matchs pour voir l'évolution des Elos.")

            # ─────────────────────────────────────────
            # GOAT / WOAT
            # ─────────────────────────────────────────
            st.markdown("---")
            st.markdown("## 🐐 GOAT & 💀 WOAT")

            timeline = []
            for player, hist in elo_history.items():
                for e in hist:
                    timeline.append({
                        "player": player,
                        "elo": e["elo"],
                        "date": datetime.strptime(e["date"], "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)
                    })
            timeline = sorted(timeline, key=lambda x: x["date"])

            if timeline:
                # GOAT
                goat_record  = None
                current_best = -999999
                for event in timeline:
                    if event["elo"] > current_best:
                        if goat_record is not None:
                            if event["player"] == goat_record["player"]:
                                # Il bat son propre record, on garde le start original
                                old_start = goat_record["start"]
                                current_best = event["elo"]
                                goat_record = {"player": event["player"], "elo": event["elo"], "start": old_start, "end": None}
                            else:
                                goat_record["end"] = event["date"]
                                current_best = event["elo"]
                                goat_record = {"player": event["player"], "elo": event["elo"], "start": event["date"], "end": None}
                        else:
                            current_best = event["elo"]
                            goat_record = {"player": event["player"], "elo": event["elo"], "start": event["date"], "end": None}
                if goat_record:
                    goat_record["end"] = now_fr()
                
                # WOAT
                woat_record   = None
                current_worst = 999999
                for event in timeline:
                    if event["elo"] < current_worst:
                        if woat_record is not None:
                            if event["player"] == woat_record["player"]:
                                old_start = woat_record["start"]
                                current_worst = event["elo"]
                                woat_record = {"player": event["player"], "elo": event["elo"], "start": old_start, "end": None}
                            else:
                                woat_record["end"] = event["date"]
                                current_worst = event["elo"]
                                woat_record = {"player": event["player"], "elo": event["elo"], "start": event["date"], "end": None}
                        else:
                            current_worst = event["elo"]
                            woat_record = {"player": event["player"], "elo": event["elo"], "start": event["date"], "end": None}
                if woat_record:
                    woat_record["end"] = now_fr()

                def duration_text(start, end):
                    delta = end - start
                    days  = delta.days
                    hours = delta.seconds // 3600
                    if days > 0:
                        return f"{days}j {hours}h"
                    return f"{hours}h"

                col1, col2 = st.columns(2)
                col1.success(
                    f"🐐 **GOAT : {goat_record['player']}**\n\n"
                    f"Elo record : **{goat_record['elo']}**\n\n"
                    f"👑 Règne : {duration_text(goat_record['start'], goat_record['end'])}"
                )
                col2.error(
                    f"💀 **WOAT : {woat_record['player']}**\n\n"
                    f"Elo minimum : **{woat_record['elo']}**\n\n"
                    f"🪦 Règne : {duration_text(woat_record['start'], woat_record['end'])}"
                )

            # ─────────────────────────────────────────
            # ANALYSE INDIVIDUELLE
            # ─────────────────────────────────────────
            st.markdown("---")
            st.markdown("### 🔍 Analyse individuelle")
            player_sel = st.selectbox("Choisir un joueur", sorted(players.keys()))

            if player_sel:
                p = player_sel

                def get_mode(m):
                    w, l, n = len(m["winners"]), len(m["losers"]), len(m.get("neutrals", []))
                    total = w + l + n
                    if n > 0:
                        return "1v1v1" if total == 3 else "FFA"
                    if w == 1 and l == 1: return "1v1"
                    if w == 2 and l == 2: return "2v2"
                    return "Autre"

                p_matchs = [m for m in history if p in m["winners"] + m["losers"] + m.get("neutrals", [])]

                if not p_matchs:
                    st.info(f"{p} n'a pas encore joué de match.")
                else:
                    st.markdown(f"#### Win rate de **{p}** par mode de jeu")
                    mode_stats = []
                    for mode in ["1v1", "2v2", "1v1v1", "Autre"]:
                        m_mode   = [m for m in p_matchs if get_mode(m) == mode]
                        played_m = len(m_mode)
                        wins_m   = sum(1 for m in m_mode if p in m["winners"])
                        if played_m > 0:
                            mode_stats.append({
                                "Mode": mode,
                                "Matchs": played_m,
                                "Victoires": wins_m,
                                "Win rate (%)": round(wins_m / played_m * 100),
                            })

                    if mode_stats:
                        st.dataframe(pd.DataFrame(mode_stats), use_container_width=True, hide_index=True)
                    else:
                        st.info("Pas assez de données par mode.")

                    st.markdown("---")
                    st.markdown(f"#### 🤝 Partenaire préféré")
                    matchs_2v2    = [m for m in p_matchs if get_mode(m) == "2v2"]
                    partner_count = {}
                    for m in matchs_2v2:
                        team = m["winners"] if p in m["winners"] else m["losers"]
                        for mate in team:
                            if mate != p:
                                partner_count[mate] = partner_count.get(mate, 0) + 1

                    if partner_count:
                        best_partner = max(partner_count, key=partner_count.get)
                        cols = st.columns(len(partner_count))
                        for i, (mate, count) in enumerate(sorted(partner_count.items(), key=lambda x: -x[1])):
                            cols[i].metric(mate, f"{count} fois", "⭐" if mate == best_partner else "")
                    else:
                        st.info("Pas de matchs 2v2 enregistrés.")

                    st.markdown("---")
                    st.markdown(f"#### ⚔️ Nemesis & Elo farming")

                    face_to_face = {}
                    for m in p_matchs:
                        if p in m["winners"]:
                            opponents = m["losers"] + m.get("neutrals", [])
                            result = "win"
                        elif p in m["losers"]:
                            opponents = m["winners"] + m.get("neutrals", [])
                            result = "loss"
                        else:
                            opponents = m["winners"] + m["losers"]
                            result = "neutral"

                        for opp in opponents:
                            if opp == p: continue
                            if opp not in face_to_face:
                                face_to_face[opp] = {"played": 0, "losses": 0, "wins": 0}
                            face_to_face[opp]["played"] += 1
                            if result == "loss":  face_to_face[opp]["losses"] += 1
                            elif result == "win": face_to_face[opp]["wins"]   += 1

                    if face_to_face:
                        nemesis      = max(face_to_face, key=lambda x: face_to_face[x]["losses"] / face_to_face[x]["played"])
                        nemesis_rate = round(face_to_face[nemesis]["losses"] / face_to_face[nemesis]["played"] * 100)
                        farming      = max(face_to_face, key=lambda x: face_to_face[x]["wins"] / face_to_face[x]["played"])
                        farming_rate = round(face_to_face[farming]["wins"] / face_to_face[farming]["played"] * 100)

                        col1, col2 = st.columns(2)
                        col1.error(f"😈 **Nemesis : {nemesis}**\n\nPerd contre lui {nemesis_rate}% du temps")
                        col2.success(f"🌾 **Elo farming : {farming}**\n\nGagne contre lui {farming_rate}% du temps")

                        df_faceoff = pd.DataFrame([
                            {
                                "Adversaire": opp,
                                "Confrontations": d["played"],
                                "Victoires": d["wins"],
                                "Défaites": d["losses"],
                                "Win rate (%)": round(d["wins"] / d["played"] * 100),
                            }
                            for opp, d in face_to_face.items()
                        ]).sort_values("Win rate (%)", ascending=False).reset_index(drop=True)
                        st.dataframe(df_faceoff, use_container_width=True, hide_index=True)
                    else:
                        st.info("Pas assez de données pour calculer nemesis / elo farming.")

# ─────────────────────────────────────────
# PAGE : JOUEURS
# ─────────────────────────────────────────
elif page == "👤 Joueurs":
    st.title("👤 Gestion des joueurs")

    st.markdown("### Ajouter un joueur")
    col1, col2, col3 = st.columns([2, 1, 1])
    new_name = col1.text_input("Nom du joueur")
    new_elo  = col2.number_input("Elo initial", value=1000, min_value=0, max_value=9999)
    if col3.button("Ajouter", type="primary"):
        if not new_name.strip():
            st.error("Le nom ne peut pas être vide.")
        elif new_name in players:
            st.error(f"'{new_name}' existe déjà.")
        else:
            players[new_name] = new_elo
            elo_history[new_name] = [{"date": now_fr().strftime("%d/%m/%Y %H:%M"), "elo": new_elo}]
            data["elo_history"] = elo_history
            save_data(data)
            st.success(f"'{new_name}' ajouté avec Elo {new_elo}.")
            st.rerun()

    st.markdown("---")
    st.markdown("### Modifier / Supprimer")

    if not players:
        st.info("Aucun joueur.")
    else:
        for name in sorted(players.keys()):
            cols = st.columns([2, 1.5, 1, 1])
            cols[0].markdown(f"**{name}**")
            new_val = cols[1].number_input("Elo", value=players[name], key=f"elo_{name}", label_visibility="collapsed")
            if cols[2].button("💾 Sauver", key=f"save_{name}"):
                players[name] = new_val
                save_data(data)
                st.success(f"Elo de '{name}' mis à jour.")
                st.rerun()
            if cols[3].button("🗑️ Supprimer", key=f"del_{name}"):
                del players[name]
                save_data(data)
                st.success(f"'{name}' supprimé.")
                st.rerun()
