import streamlit as st
import json
import os
import math
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
PASSWORD = "canasta2024"   # Change ici ton mot de passe
K = 30
DATA_FILE = "data.json"

st.set_page_config(page_title="Classement Canasta", page_icon="🃏", layout="wide")

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
# DONNÉES
# ─────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"players": {}, "history": [], "elo_history": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if "data" not in st.session_state:
    st.session_state.data = load_data()

data = st.session_state.data
players = data["players"]
history = data["history"]
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

    # Arrondir
    for p in winners + losers + neutrals:
        players[p] = round(players[p])

    # Enregistrer le delta
    deltas = {n: players[n] - snapshot[n] for n in snapshot}

    # Historique match
    entry = {
        "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "winners": winners,
        "losers": losers,
        "neutrals": neutrals,
        "deltas": deltas,
        "snapshot_before": snapshot,
    }
    history.insert(0, entry)

    # Historique Elo par joueur
    ts = datetime.now().strftime("%d/%m/%Y %H:%M")
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
        cols = st.columns([0.5, 2, 1.5, 1.5, 1.5])
        cols[0].markdown("**#**")
        cols[1].markdown("**Joueur**")
        cols[2].markdown("**Elo**")
        cols[3].markdown("**Matchs joués**")
        cols[4].markdown("**Win rate**")
        st.markdown("---")

        for i, (name, elo) in enumerate(sorted_players):
            rank = medals[i] if i < 3 else str(i + 1)

            # Stats depuis l'historique
            played = sum(1 for m in history if name in m["winners"] + m["losers"] + m["neutrals"])
            wins   = sum(1 for m in history if name in m["winners"])
            winrate = f"{round(wins/played*100)}%" if played > 0 else "—"

            cols = st.columns([0.5, 2, 1.5, 1.5, 1.5])
            cols[0].markdown(rank)
            cols[1].markdown(f"**{name}**")
            cols[2].markdown(f"`{elo}`")
            cols[3].markdown(str(played))
            cols[4].markdown(winrate)



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

        # Vérifications
        all_selected = winners + losers + neutrals
        overlap = len(all_selected) != len(set(all_selected))

        if winners and losers:
            if overlap:
                st.error("Un joueur ne peut pas être dans deux catégories à la fois.")
            else:
                # Aperçu des changements attendus
                st.markdown("### Aperçu des changements")

                tmp_players = dict(players)

                def sim_elo(tmp, w, l, n):
                    def avg(names): return sum(tmp[x] for x in names) / len(names)
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

                preview = sim_elo(tmp_players, winners, losers, neutrals)
                preview_cols = st.columns(len(all_selected))
                for i, name in enumerate(all_selected):
                    delta = preview.get(name, 0)
                    sign = "+" if delta >= 0 else ""
                    color = "green" if delta > 0 else ("red" if delta < 0 else "gray")
                    preview_cols[i].metric(name, players[name], f"{sign}{delta}")

                st.markdown("")
                if st.button("✅ Valider le match", type="primary"):
                    update_elo(winners, losers, neutrals)
                    st.success("Match enregistré !")
                    st.rerun()

        # Historique récent
        if history:
            st.markdown("---")
            st.markdown("### Derniers matchs")
            for m in history[:10]:
                w = ", ".join(m["winners"])
                l = ", ".join(m["losers"])
                n = f" | Neutres: {', '.join(m['neutrals'])}" if m["neutrals"] else ""
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
        # Stats globales
        total_matchs = len(history)
        st.metric("Matchs joués", total_matchs)

        if history:
            st.markdown("---")

            # Tableau stats par joueur
            stats = []
            for name in players:
                played = sum(1 for m in history if name in m["winners"] + m["losers"] + m["neutrals"])
                wins   = sum(1 for m in history if name in m["winners"])
                losses = sum(1 for m in history if name in m["losers"])
                neutral= sum(1 for m in history if name in m.get("neutrals", []))
                winrate= round(wins / played * 100) if played > 0 else 0
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

            # Graphique évolution Elo
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

            # Win rate camembert
            st.markdown("### Win rate comparé")
            df_pie = df_stats[df_stats["Victoires"] > 0]
            if not df_pie.empty:
                fig2 = px.pie(df_pie, names="Joueur", values="Victoires", title="Répartition des victoires")
                fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig2, use_container_width=True)

# ─────────────────────────────────────────
# PAGE : JOUEURS
# ─────────────────────────────────────────
elif page == "👤 Joueurs":
    st.title("👤 Gestion des joueurs")

    # Ajouter
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
            elo_history[new_name] = [{"date": datetime.now().strftime("%d/%m/%Y %H:%M"), "elo": new_elo}]
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
