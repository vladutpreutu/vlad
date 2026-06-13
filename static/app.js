const API_URL = "";

// --- COMUTARE VIZUALIZARE ---
function toggleAuth(view) {
    document.getElementById("auth-section").classList.toggle("d-none", view !== 'login');
    document.getElementById("register-section").classList.toggle("d-none", view !== 'register');
}

// --- LOGARE ---
async function login() {
    const email = document.getElementById("email").value;
    const parola = document.getElementById("parola").value;
    const formData = new URLSearchParams();
    formData.append("username", email);
    formData.append("password", parola);

    const res = await fetch(`${API_URL}/autentificare`, { method: "POST", body: formData });
    if (res.ok) {
        const data = await res.json();
        localStorage.setItem("token", data.access_token);
        location.reload();
    } else { alert("Login eșuat!"); }
}

// --- ÎNREGISTRARE ---
async function register() {
    const email = document.getElementById("reg-email").value;
    const parola = document.getElementById("reg-parola").value;

    const res = await fetch(`${API_URL}/inregistrare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email, parola: parola })
    });
    
    if (res.ok) {
        alert("Cont creat! Acum te poți loga.");
        toggleAuth('login');
    } else { alert("Eroare la înregistrare."); }
}

// --- SARCINI ---
async function loadTasks() {
    const token = localStorage.getItem("token");
    const filtrat = document.getElementById("filtru").checked;
    let url = `${API_URL}/sarcini${filtrat ? "?doar_nefinalizate=true" : ""}`;
    
    const res = await fetch(url, { headers: { "Authorization": `Bearer ${token}` } });
    if (res.ok) {
        const tasks = await res.json();
        const list = document.getElementById("task-list");
        list.innerHTML = "";
        tasks.forEach(t => {
            list.innerHTML += `<li class="list-group-item d-flex justify-content-between">
                <span style="${t.finalizata ? 'text-decoration:line-through' : ''}">${t.titlu}</span>
                <div>
                    ${!t.finalizata ? `<button onclick="finalizeTask(${t.id})" class="btn btn-sm btn-outline-success">OK</button>` : ''}
                    <button onclick="deleteTask(${t.id})" class="btn btn-sm btn-outline-danger">Șterge</button>
                </div>
            </li>`;
        });
    }
}

async function addTask() {
    const titlu = document.getElementById("titlu-nou").value;
    await fetch(`${API_URL}/sarcini`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${localStorage.getItem("token")}`, "Content-Type": "application/json" },
        body: JSON.stringify({ titlu })
    });
    loadTasks();
}

async function finalizeTask(id) {
    await fetch(`${API_URL}/sarcini/${id}/finalizeaza`, { method: "PATCH", headers: { "Authorization": `Bearer ${localStorage.getItem("token")}` } });
    loadTasks();
}

async function deleteTask(id) {
    await fetch(`${API_URL}/sarcini/${id}`, { method: "DELETE", headers: { "Authorization": `Bearer ${localStorage.getItem("token")}` } });
    loadTasks();
}

function logout() { localStorage.removeItem("token"); location.reload(); }

// INITIALIZARE
if (localStorage.getItem("token")) {
    document.getElementById("auth-section").classList.add("d-none");
    document.getElementById("task-section").classList.remove("d-none");
    loadTasks();
}
