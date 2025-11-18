from flask import Flask, request, jsonify, render_template_string
import time
import os

app = Flask(__name__)

# "Base de datos" super simple en memoria
text_answers = []  # lista de strings con las respuestas abiertas
votes = {"a_favor": 0, "en_contra": 0}

# Estado global para controlar el flujo
state = {
    "mode": "collect",   # "collect" o "results"
    "deadline": None     # timestamp para la cuenta regresiva (opcional)
}

# ================== PÁGINA PRINCIPAL (PARTICIPANTES) ==================

HTML_PAGE = r"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8" />
    <title>Encuesta IA</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            margin: 0;
            padding: 0;
            background: #f4f6fb;
            display: flex;
            justify-content: center;
        }
        .container {
            max-width: 900px;
            width: 100%;
            padding: 24px 16px 40px;
        }
        h1, h2 {
            text-align: center;
            color: #222;
        }
        .card {
            background: #ffffff;
            border-radius: 16px;
            padding: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.06);
            margin-bottom: 20px;
        }
        label {
            font-weight: 600;
            display: block;
            margin-bottom: 8px;
        }
        textarea {
            width: 100%;
            min-height: 90px;
            border-radius: 12px;
            border: 1px solid #cbd5e1;
            padding: 10px;
            font-size: 14px;
            resize: vertical;
        }
        button {
            border-radius: 999px;
            border: none;
            padding: 10px 20px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 10px;
        }
        button.primary {
            background: #2563eb;
            color: white;
        }
        button.primary:disabled {
            background: #94a3b8;
            cursor: default;
        }
        .options {
            display: flex;
            gap: 16px;
            margin-top: 8px;
            flex-wrap: wrap;
        }
        .option-box {
            flex: 1 1 150px;
            padding: 18px 16px;
            border-radius: 16px;
            border: 2px solid #e2e8f0;
            text-align: center;
            font-weight: 600;
            cursor: pointer;
            user-select: none;
            transition: transform 0.1s ease, box-shadow 0.1s ease, border-color 0.1s ease;
            background: white;
        }
        .option-box:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 10px rgba(0,0,0,0.08);
        }
        .option-box.selected {
            border-color: #2563eb;
            box-shadow: 0 0 0 1px #2563eb55;
        }
        .timer {
            text-align: center;
            font-size: 16px;
            font-weight: 600;
            margin: 12px 0;
            color: #334155;
        }
        .results-section {
            display: none;
        }
        .answers-list {
            margin-top: 10px;
            padding-left: 18px;
        }
        .answers-list li {
            margin-bottom: 6px;
        }
        .small-note {
            font-size: 12px;
            color: #64748b;
            margin-top: 6px;
        }
    </style>
</head>
<body>
<div class="container">
    <h1>Encuesta sobre IA</h1>

    <div class="timer">
        Tiempo restante para responder: <span id="countdown">--</span> segundos
    </div>
    <p class="small-note" style="text-align:center;">
        Responde ahora. Cuando la persona que dirige la actividad lo decida, se mostrarán los resultados en esta misma página.
    </p>

    <!-- Pregunta 1 -->
    <div class="card" id="q1-card">
        <h2>Pregunta 1</h2>
        <label for="q1">¿Qué problemas han tenido con la IA?</label>
        <textarea id="q1" placeholder="Escribe tu experiencia aquí..."></textarea>
        <button class="primary" id="q1-submit">Enviar respuesta</button>
        <div class="small-note" id="q1-status"></div>
    </div>

    <!-- Pregunta 2 -->
    <div class="card" id="q2-card">
        <h2>Pregunta 2</h2>
        <p>¿Estás a favor o en contra del rechazo de la cobertura del siniestro?</p>
        <div class="options">
            <div class="option-box" id="btn-a-favor" data-choice="a_favor">
                A favor
            </div>
            <div class="option-box" id="btn-en-contra" data-choice="en_contra">
                En contra
            </div>
        </div>
        <div class="small-note" id="q2-status">Haz clic en una de las opciones.</div>
    </div>

    <!-- Resultados -->
    <div class="card results-section" id="results-card">
        <h2>Resultados</h2>

        <h3>Respuestas a la pregunta 1</h3>
        <ul class="answers-list" id="answers-list">
            <!-- Se llenará por JS -->
        </ul>

        <hr style="margin: 18px 0;">

        <h3>Votos a favor / en contra</h3>
        <canvas id="votesChart" height="120"></canvas>
        <p class="small-note">
            El gráfico muestra cuántas personas eligieron cada opción.
        </p>
    </div>
</div>

<script>
    let votesChart = null;

    const countdownSpan = document.getElementById("countdown");
    const q1Card = document.getElementById("q1-card");
    const q2Card = document.getElementById("q2-card");
    const resultsCard = document.getElementById("results-card");

    const q1Textarea = document.getElementById("q1");
    const q1Submit = document.getElementById("q1-submit");
    const q1Status = document.getElementById("q1-status");

    const btnAFavor = document.getElementById("btn-a-favor");
    const btnEnContra = document.getElementById("btn-en-contra");
    const q2Status = document.getElementById("q2-status");

    const answersList = document.getElementById("answers-list");

    let hasSubmittedText = false;
    let hasVoted = false;
    let selectedChoice = null;
    let alreadyShowingResults = false;

    // Enviar respuesta de texto
    q1Submit.addEventListener("click", () => {
        const text = q1Textarea.value.trim();
        if (!text) {
            q1Status.textContent = "Escribe algo antes de enviar.";
            return;
        }
        if (hasSubmittedText) {
            q1Status.textContent = "Ya enviaste tu respuesta. ¡Gracias!";
            return;
        }
        fetch("/answer_text", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({answer: text})
        }).then(res => {
            if (res.ok) {
                hasSubmittedText = true;
                q1Status.textContent = "Respuesta enviada. ¡Gracias!";
                q1Textarea.disabled = true;
                q1Submit.disabled = true;
            } else {
                q1Status.textContent = "Hubo un problema al enviar. Intenta de nuevo.";
            }
        }).catch(() => {
            q1Status.textContent = "Error de conexión al enviar.";
        });
    });

    // Selección de voto
    function selectOption(box) {
        if (hasVoted) {
            q2Status.textContent = "Ya registraste tu voto. ¡Gracias!";
            return;
        }
        selectedChoice = box.dataset.choice;

        btnAFavor.classList.remove("selected");
        btnEnContra.classList.remove("selected");
        box.classList.add("selected");

        fetch("/vote", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({choice: selectedChoice})
        }).then(res => {
            if (res.ok) {
                hasVoted = true;
                q2Status.textContent = "Voto registrado. ¡Gracias!";
            } else {
                q2Status.textContent = "No se pudo registrar el voto. Intenta de nuevo.";
            }
        }).catch(() => {
            q2Status.textContent = "Error de conexión al registrar el voto.";
        });
    }

    btnAFavor.addEventListener("click", () => selectOption(btnAFavor));
    btnEnContra.addEventListener("click", () => selectOption(btnEnContra));

    // Consultar estado global al servidor
    async function pollState() {
        try {
            const res = await fetch("/state");
            const data = await res.json();

            // Actualizar contador (si hay deadline)
            if (typeof data.seconds_left === "number" && data.seconds_left >= 0) {
                countdownSpan.textContent = data.seconds_left;
            } else {
                countdownSpan.textContent = "--";
            }

            if (data.mode === "results" && !alreadyShowingResults) {
                alreadyShowingResults = true;
                showResults();
            }
        } catch (e) {
            // nada
        } finally {
            setTimeout(pollState, 2000);
        }
    }

    // Obtener resultados del backend
    function fetchResults() {
        return fetch("/results")
            .then(res => res.json())
            .catch(() => ({answers_text: [], votes: {a_favor: 0, en_contra: 0}}));
    }

    // Mostrar resultados en pantalla y gráfico
    async function showResults() {
        q1Card.style.display = "none";
        q2Card.style.display = "none";
        resultsCard.style.display = "block";

        const data = await fetchResults();

        // Llenar lista de respuestas
        answersList.innerHTML = "";
        if (data.answers_text.length === 0) {
            const li = document.createElement("li");
            li.textContent = "Aún no hay respuestas.";
            answersList.appendChild(li);
        } else {
            data.answers_text.forEach((ans) => {
                const li = document.createElement("li");
                li.textContent = ans;
                answersList.appendChild(li);
            });
        }

        // Crear gráfico
        const ctx = document.getElementById("votesChart").getContext("2d");
        const aFavor = data.votes.a_favor || 0;
        const enContra = data.votes.en_contra || 0;

        if (votesChart) {
            votesChart.destroy();
        }

        votesChart = new Chart(ctx, {
            type: "bar",
            data: {
                labels: ["A favor", "En contra"],
                datasets: [{
                    label: "Número de personas",
                    data: [aFavor, enContra]
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                }
            }
        });
    }

    // Empezar a consultar el estado global
    pollState();
</script>
</body>
</html>
"""

# ================== PÁGINA ADMIN ==================

ADMIN_PAGE = r"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8" />
    <title>Admin Encuesta IA</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
        body {
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            margin: 0;
            padding: 0;
            background: #0f172a;
            color: #e5e7eb;
            display: flex;
            justify-content: center;
        }
        .container {
            max-width: 600px;
            width: 100%;
            padding: 24px 16px 40px;
        }
        h1 {
            text-align: center;
            margin-bottom: 24px;
        }
        .card {
            background: #020617;
            border-radius: 16px;
            padding: 20px;
            box-shadow: 0 4px 12px rgba(15,23,42,0.6);
            margin-bottom: 16px;
        }
        button {
            border-radius: 999px;
            border: none;
            padding: 10px 20px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            margin-right: 10px;
        }
        button.primary {
            background: #22c55e;
            color: #022c22;
        }
        button.secondary {
            background: #3b82f6;
            color: white;
        }
        button.danger {
            background: #ef4444;
            color: white;
        }
        .status {
            margin-top: 10px;
            font-size: 14px;
            color: #e5e7eb;
        }
        .timer {
            font-size: 18px;
            font-weight: 700;
            margin-top: 8px;
        }
        a {
            color: #38bdf8;
        }
    </style>
</head>
<body>
<div class="container">
    <h1>Panel de control - Encuesta IA</h1>

    <div class="card">
        <p>
            Comparte este enlace (o genera un código QR con él) para los participantes:
        </p>
        <p><strong id="public-url"></strong></p>
    </div>

    <div class="card">
        <h2>Control del tiempo</h2>
        <button class="primary" id="btn-start-60">Iniciar cuenta regresiva (60s)</button>
        <button class="secondary" id="btn-show-results">Mostrar resultados ahora</button>
        <button class="danger" id="btn-reset">Reiniciar encuesta (borra respuestas)</button>
        <div class="timer" id="admin-timer">Tiempo restante: -- s</div>
        <div class="status" id="admin-status"></div>
    </div>
</div>

<script>
    const btnStart60 = document.getElementById("btn-start-60");
    const btnShowResults = document.getElementById("btn-show-results");
    const btnReset = document.getElementById("btn-reset");
    const adminTimer = document.getElementById("admin-timer");
    const adminStatus = document.getElementById("admin-status");
    const publicUrlEl = document.getElementById("public-url");

    // Mostrar URL pública aproximada
    publicUrlEl.textContent = window.location.origin + "/";

    btnStart60.addEventListener("click", async () => {
        try {
            const res = await fetch("/admin/start_60", {method: "POST"});
            if (res.ok) {
                adminStatus.textContent = "Cuenta regresiva de 60 segundos iniciada.";
            } else {
                adminStatus.textContent = "No se pudo iniciar la cuenta regresiva.";
            }
        } catch {
            adminStatus.textContent = "Error de conexión.";
        }
    });

    btnShowResults.addEventListener("click", async () => {
        try {
            const res = await fetch("/admin/show_results", {method: "POST"});
            if (res.ok) {
                adminStatus.textContent = "Resultados mostrados para todos.";
            } else {
                adminStatus.textContent = "No se pudo cambiar a modo resultados.";
            }
        } catch {
            adminStatus.textContent = "Error de conexión.";
        }
    });

    btnReset.addEventListener("click", async () => {
        if (!confirm("¿Seguro que quieres borrar todas las respuestas y reiniciar la encuesta?")) {
            return;
        }
        try {
            const res = await fetch("/admin/reset", {method: "POST"});
            if (res.ok) {
                adminStatus.textContent = "Encuesta reiniciada.";
            } else {
                adminStatus.textContent = "No se pudo reiniciar.";
            }
        } catch {
            adminStatus.textContent = "Error de conexión.";
        }
    });

    async function pollState() {
        try {
            const res = await fetch("/state");
            const data = await res.json();
            if (typeof data.seconds_left === "number" && data.seconds_left >= 0) {
                adminTimer.textContent = "Tiempo restante: " + data.seconds_left + " s";
            } else {
                adminTimer.textContent = "Tiempo restante: -- s";
            }
        } catch (e) {
            // ignorar
        } finally {
            setTimeout(pollState, 2000);
        }
    }

    pollState();
</script>
</body>
</html>
"""

# ================== RUTAS BACKEND ==================

@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_PAGE)

@app.route("/admin", methods=["GET"])
def admin():
    return render_template_string(ADMIN_PAGE)

@app.route("/answer_text", methods=["POST"])
def answer_text():
    data = request.get_json(force=True, silent=True) or {}
    answer = (data.get("answer") or "").strip()
    if answer:
        text_answers.append(answer)
    return ("", 204)

@app.route("/vote", methods=["POST"])
def vote():
    data = request.get_json(force=True, silent=True) or {}
    choice = data.get("choice")
    if choice in votes:
        votes[choice] += 1
    return ("", 204)

@app.route("/results", methods=["GET"])
def results():
    return jsonify({"answers_text": text_answers, "votes": votes})

@app.route("/state", methods=["GET"])
def get_state():
    """Devuelve el modo actual y segundos restantes (para el contador global)."""
    mode = state["mode"]
    deadline = state["deadline"]
    seconds_left = None
    if deadline is not None:
        remaining = int(round(deadline - time.time()))
        if remaining < 0:
            remaining = 0
        seconds_left = remaining
    return jsonify({"mode": mode, "seconds_left": seconds_left})

# --------- Rutas de control (admin) ---------

@app.route("/admin/start_60", methods=["POST"])
def admin_start_60():
    """Inicia una cuenta regresiva de 60 segundos (solo visual)."""
    state["mode"] = "collect"
    state["deadline"] = time.time() + 60
    return ("", 204)

@app.route("/admin/show_results", methods=["POST"])
def admin_show_results():
    """Cambia a modo resultados para todos los clientes."""
    state["mode"] = "results"
    state["deadline"] = None
    return ("", 204)

@app.route("/admin/reset", methods=["POST"])
def admin_reset():
    """Borra respuestas y vuelve a modo de recolección sin cuenta regresiva."""
    text_answers.clear()
    votes["a_favor"] = 0
    votes["en_contra"] = 0
    state["mode"] = "collect"
    state["deadline"] = None
    return ("", 204)

if __name__ == "__main__":
    # Para local o Render/otro PaaS
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

