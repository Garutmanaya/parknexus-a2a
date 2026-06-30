import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const HOST_URL = import.meta.env.VITE_HOST_AGENT_URL || "https://localhost:8030";

async function apiGet(path) {
  const response = await fetch(`${HOST_URL}${path}`, { method: "GET" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || JSON.stringify(payload));
  return payload;
}

async function apiPost(path, body) {
  const response = await fetch(`${HOST_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || JSON.stringify(payload));
  return payload;
}

async function apiPut(path, body) {
  const response = await fetch(`${HOST_URL}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || JSON.stringify(payload));
  return payload;
}

async function apiDelete(path) {
  const response = await fetch(`${HOST_URL}${path}`, { method: "DELETE" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || JSON.stringify(payload));
  return payload;
}

function statusClass(status, selected, recommended) {
  if (selected) return "slot selected";
  if (recommended) return "slot recommended";
  if (status === "AVAILABLE") return "slot available";
  if (status === "HELD") return "slot held";
  if (status === "RESERVED" || status === "OCCUPIED") return "slot reserved";
  return "slot blocked";
}

function LoginPage({ onUserLogin, onAdminLogin }) {
  const [mode, setMode] = useState("user");
  const [userId, setUserId] = useState("ui_user_001");
  const [password, setPassword] = useState("password123");
  const [adminName, setAdminName] = useState("admin");
  const [adminPassword, setAdminPassword] = useState("admin123");
  const [error, setError] = useState("");

  async function loginUser() {
    setError("");
    const result = await apiPost("/user/login", { user_id: userId, password });
    if (!result.authenticated) {
      setError(result.message || "Invalid user credentials");
      return;
    }
    onUserLogin(result.user);
  }

  async function loginAdmin() {
    setError("");
    const result = await apiPost("/admin/login", { username: adminName, password: adminPassword });
    if (!result.authenticated) {
      setError(result.message || "Invalid admin credentials");
      return;
    }
    onAdminLogin({ username: adminName });
  }

  return (
    <div className="loginPage">
      <div className="loginCard">
        <h1>ParkNexus A2A</h1>
        <p>Secure agentic parking platform</p>
        <div className="tabs">
          <button className={mode === "user" ? "active" : ""} onClick={() => setMode("user")}>User Login</button>
          <button className={mode === "admin" ? "active" : ""} onClick={() => setMode("admin")}>Admin Login</button>
        </div>
        {mode === "user" ? (
          <div className="formStack">
            <input value={userId} onChange={(e) => setUserId(e.target.value)} placeholder="User ID" />
            <input value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" type="password" />
            <button className="primaryBtn" onClick={loginUser}>Login</button>
          </div>
        ) : (
          <div className="formStack">
            <input value={adminName} onChange={(e) => setAdminName(e.target.value)} placeholder="Admin username" />
            <input value={adminPassword} onChange={(e) => setAdminPassword(e.target.value)} placeholder="Admin password" type="password" />
            <button className="primaryBtn" onClick={loginAdmin}>Admin Login</button>
          </div>
        )}
        {error && <div className="errorBox">{error}</div>}
      </div>
    </div>
  );
}

function AdminPortal({ admin, onLogout }) {
  const [users, setUsers] = useState([]);
  const [agents, setAgents] = useState([]);
  const [form, setForm] = useState({
    user_id: "ui_user_001",
    password: "password123",
    email: "demo@example.com",
    display_name: "Demo User",
    first_name: "Demo",
    last_name: "User",
    phone_number: "",
    address: "",
  });
  const [status, setStatus] = useState("Ready");

  async function loadUsers() {
    const result = await apiGet("/admin/users");
    setUsers(result.users || []);
  }

  async function loadAgents() {
    const result = await apiGet("/admin/agents");
    setAgents(result.agents || []);
  }

  async function createUser() {
    await apiPost("/admin/users", form);
    setStatus(`Created/updated user ${form.user_id}`);
    await loadUsers();
  }

  async function updateUser(user, changes) {
    await apiPut("/admin/users", { user_id: user.user_id, ...changes });
    setStatus(`Updated user ${user.user_id}`);
    await loadUsers();
  }

  async function deleteUser(userId) {
    await apiDelete(`/admin/users/${encodeURIComponent(userId)}`);
    setStatus(`Deleted user ${userId}`);
    await loadUsers();
  }

  useEffect(() => {
    loadUsers().catch((e) => setStatus(`User load failed: ${e.message}`));
    loadAgents().catch((e) => setStatus(`Agent load failed: ${e.message}`));
  }, []);

  return (
    <div className="adminShell">
      <header className="portalHeader">
        <div><h1>ParkNexus Admin</h1><p>Signed in as {admin.username}</p></div>
        <button onClick={onLogout}>Logout</button>
      </header>
      <main className="adminGrid">
        <section className="card">
          <h2>Create / Update User</h2>
          <div className="formGrid">
            {Object.keys(form).map((key) => (
              <input key={key} value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} placeholder={key} type={key === "password" ? "password" : "text"} />
            ))}
          </div>
          <button className="primaryBtn" onClick={createUser}>Save User</button>
          <p className="muted">Recommended fields: user_id, password, email, first/last name. Phone and address are optional for alerts/logistics.</p>
        </section>

        <section className="card">
          <h2>User Management</h2>
          <button className="smallBtn" onClick={loadUsers}>Refresh Users</button>
          <div className="tableList">
            {users.map((user) => (
              <div className="tableRow" key={user.user_id}>
                <div><b>{user.user_id}</b><span>{user.display_name} • {user.email}</span><small>{user.phone_number || "No phone"} • {user.address || "No address"}</small></div>
                <div className="rowActions">
                  <button onClick={() => updateUser(user, { is_active: !user.is_active })}>{user.is_active ? "Disable" : "Enable"}</button>
                  <button onClick={() => setForm({ ...form, ...user, password: "" })}>Edit</button>
                  <button className="danger" onClick={() => deleteUser(user.user_id)}>Delete</button>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="card wideAdmin">
          <h2>Agent Management</h2>
          <button className="smallBtn" onClick={loadAgents}>Refresh Agents</button>
          <div className="tableList">
            {agents.map((agent) => (
              <div className="tableRow" key={agent.name}>
                <div><b>{agent.name}</b><span>{agent.url}</span><small>{(agent.skills || []).map((s) => s.id).join(", ")}</small></div>
                <div className="pill">{agent.capabilities?.streaming ? "Streaming" : "Sync"}</div>
              </div>
            ))}
          </div>
        </section>
      </main>
      <div className="statusBar">{status}</div>
    </div>
  );
}

function UserPortal({ user, onLogout }) {
  const [message, setMessage] = useState("Find me cheap EV parking under $20 per hour");
  const [conversation, setConversation] = useState([]);
  const [searchResult, setSearchResult] = useState(null);
  const [layout, setLayout] = useState(null);
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [selectedProviderAgent, setSelectedProviderAgent] = useState(null);
  const [activeLevel, setActiveLevel] = useState("");
  const [transactions, setTransactions] = useState([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Ready");

  const providerSummaries = useMemo(() => {
    const map = new Map();
    for (const slot of searchResult?.slots || []) {
      const key = slot.provider_agent;
      const current = map.get(key) || { provider_agent: key, provider_url: slot.provider_url, count: 0, min_price: null, nearest_distance: null };
      const price = Number(slot.estimated_price || slot.hourly_rate || 0);
      current.count += 1;
      current.min_price = current.min_price === null ? price : Math.min(current.min_price, price);
      current.nearest_distance = current.nearest_distance === null ? slot.distance_to_entrance_meters : Math.min(current.nearest_distance, slot.distance_to_entrance_meters);
      map.set(key, current);
    }
    return Array.from(map.values());
  }, [searchResult]);

  const recommendedSlotCodes = useMemo(() => {
    const values = new Set();
    for (const slot of searchResult?.slots || []) {
      if (!selectedProviderAgent || slot.provider_agent === selectedProviderAgent) values.add(slot.slot_code);
    }
    return values;
  }, [searchResult, selectedProviderAgent]);

  const currentGarage = layout?.garages?.[0];
  const levels = currentGarage?.levels || [];
  const currentLevel = levels.find((level) => level.name === activeLevel) || levels[0];

  function addConversation(role, text) {
    setConversation((previous) => [{ role, text, time: new Date().toLocaleTimeString() }, ...previous].slice(0, 20));
  }

  async function refreshTransactions() {
    const payload = await apiGet(`/transactions?user_id=${encodeURIComponent(user.user_id)}&limit=5`);
    setTransactions(payload.transactions || []);
  }

  async function loadGarageLayout(providerAgent) {
    if (!providerAgent) return;
    const data = await apiPost("/garage/layout", { provider_agent: providerAgent });
    setLayout(data);
    setActiveLevel(data.garages?.[0]?.levels?.[0]?.name || "");
  }

  async function askHostAgent() {
    if (!message.trim()) return;
    setBusy(true);
    setStatus("Searching through Host Agent...");
    addConversation("user", message);
    try {
      const result = await apiPost("/parking/chat", { message });
      setSearchResult(result);
      if (!result.slots || result.slots.length === 0) {
        setLayout(null);
        setSelectedSlot(null);
        setSelectedProviderAgent(null);
        setActiveLevel("");
        addConversation("agent", "No matching slots found.");
        setStatus("Search completed: 0 slots");
        return;
      }
      const firstSlot = result.slots[0];
      setSelectedProviderAgent(firstSlot.provider_agent);
      setSelectedSlot(firstSlot);
      await loadGarageLayout(firstSlot.provider_agent);
      addConversation("agent", `Found ${result.count || 0} matching slots.`);
      setStatus(`Search completed: ${result.count || 0} slots`);
    } catch (error) {
      addConversation("agent", `Search failed: ${error.message}`);
      setStatus(`Search failed: ${error.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function holdSelectedSlot() {
    if (!selectedSlot) return;
    setBusy(true);
    try {
      const result = await apiPost("/parking/hold", { provider_url: selectedSlot.provider_url, slot_code: selectedSlot.slot_code, user_id: user.user_id, hold_minutes: 5 });
      addConversation("agent", `Held ${selectedSlot.slot_code}. Hold ID: ${result.hold_id}`);
      setStatus(`Held ${selectedSlot.slot_code}. Alert logged for ${user.email}`);
      await refreshTransactions();
      await loadGarageLayout(selectedSlot.provider_agent);
    } catch (error) {
      setStatus(`Hold failed: ${error.message}`);
      addConversation("agent", `Hold failed: ${error.message}`);
    } finally { setBusy(false); }
  }

  async function confirmHold(transaction) {
    setBusy(true);
    try {
      const result = await apiPost("/parking/confirm", { provider_url: transaction.provider_url, hold_id: transaction.hold_id, user_id: user.user_id, reserved_minutes: 120 });
      addConversation("agent", `Confirmed ${transaction.slot_code}. Reservation ID: ${result.reservation_id}`);
      setStatus(`Confirmed ${transaction.slot_code}. Alert logged for ${user.email}`);
      await refreshTransactions();
      if (transaction.provider_agent) await loadGarageLayout(transaction.provider_agent);
    } catch (error) {
      setStatus(`Confirm failed: ${error.message}`);
      addConversation("agent", `Confirm failed: ${error.message}`);
    } finally { setBusy(false); }
  }

  async function reserveSelectedSlot() {
    if (!selectedSlot) return;
    setBusy(true);
    try {
      const hold = await apiPost("/parking/hold", { provider_url: selectedSlot.provider_url, slot_code: selectedSlot.slot_code, user_id: user.user_id, hold_minutes: 5 });
      const reservation = await apiPost("/parking/confirm", { provider_url: selectedSlot.provider_url, hold_id: hold.hold_id, user_id: user.user_id, reserved_minutes: 120 });
      addConversation("agent", `Reserved ${selectedSlot.slot_code}. Reservation ID: ${reservation.reservation_id}`);
      setStatus(`Reserved ${selectedSlot.slot_code}. Alert logged for ${user.email}`);
      await refreshTransactions();
      await loadGarageLayout(selectedSlot.provider_agent);
    } catch (error) {
      setStatus(`Reservation failed: ${error.message}`);
      addConversation("agent", `Reservation failed: ${error.message}`);
    } finally { setBusy(false); }
  }

  async function cancelOrRelease(transaction) {
    setBusy(true);
    try {
      if (transaction.hold_id && transaction.status === "HELD") {
        await apiPost("/parking/hold/cancel", { provider_url: transaction.provider_url, hold_id: transaction.hold_id, user_id: user.user_id });
        addConversation("agent", `Cancelled hold ${transaction.hold_id}`);
      } else {
        await apiPost("/parking/release", { provider_url: transaction.provider_url, slot_code: transaction.slot_code, user_id: user.user_id, reason: "Cancelled from UI history" });
        addConversation("agent", `Released ${transaction.slot_code}`);
      }
      setStatus("Cancellation completed");
      await refreshTransactions();
      if (transaction.provider_agent) await loadGarageLayout(transaction.provider_agent);
    } catch (error) {
      setStatus(`Cancel failed: ${error.message}`);
      addConversation("agent", `Cancel failed: ${error.message}`);
    } finally { setBusy(false); }
  }

  useEffect(() => { refreshTransactions().catch(() => {}); }, []);

  return (
    <div className="appShell">
      <aside className="leftPane">
        <div className="brand"><div><h1>ParkNexus A2A</h1><p>{user.display_name} • {user.email}</p></div><button onClick={onLogout}>Logout</button></div>
        <section className="card askCard"><h2>Ask Host Agent</h2><textarea value={message} onChange={(e) => setMessage(e.target.value)} /><button className="primaryBtn" onClick={askHostAgent} disabled={busy}>Ask</button></section>
        <section className="card"><h2>Conversation</h2><div className="conversation">{conversation.length === 0 && <p className="muted">No messages yet.</p>}{conversation.map((item, index) => <div key={index} className={`message ${item.role}`}><span>{item.time}</span><p>{item.text}</p></div>)}</div></section>
        <section className="card"><h2>Last 5 Transactions</h2><button className="smallBtn" onClick={refreshTransactions}>Refresh</button><div className="history">{transactions.length === 0 && <p className="muted">No transactions yet.</p>}{transactions.map((item) => <div className="historyItem" key={item.transaction_id}><b>{item.transaction_type}</b><span>{item.slot_code}</span><small>{item.status}</small>{item.hold_id && <small>Hold: {item.hold_id}</small>}{item.reservation_id && <small>Reservation: {item.reservation_id}</small>}{item.status === "HELD" && <button onClick={() => confirmHold(item)} disabled={busy}>Confirm Hold</button>}{!["CANCELLED", "RELEASED"].includes(item.status) && <button onClick={() => cancelOrRelease(item)} disabled={busy}>Cancel / Release</button>}</div>)}</div></section>
      </aside>
      <main className="rightPane">
        <div className="topStatus"><span>{status}</span><span>{busy ? "Working" : "Online"}</span></div>
        <section className="providerGrid">{providerSummaries.length === 0 && <div className="emptyState">Ask a question to discover providers and slots.</div>}{providerSummaries.map((p) => <button key={p.provider_agent} className={selectedProviderAgent === p.provider_agent ? "providerCard active" : "providerCard"} onClick={() => {setSelectedProviderAgent(p.provider_agent); setSelectedSlot(null); loadGarageLayout(p.provider_agent).catch(e=>setStatus(`Layout failed: ${e.message}`));}}><b>{p.provider_agent}</b><span>{p.count} matching slots</span><span>from ${p.min_price}</span><span>{p.nearest_distance}m nearest</span></button>)}</section>
        <section className="contentGrid"><div className="card resultsCard"><h2>Recommended Slots</h2><div className="recommendations">{(searchResult?.slots || []).slice(0,10).map((slot)=><button key={`${slot.provider_agent}-${slot.slot_code}`} className={selectedSlot?.slot_code === slot.slot_code ? "recommendation selectedRecommendation" : "recommendation"} onClick={()=>{setSelectedSlot(slot); setSelectedProviderAgent(slot.provider_agent); loadGarageLayout(slot.provider_agent).catch(e=>setStatus(`Layout failed: ${e.message}`));}}><b>{slot.slot_code}</b><span>{slot.provider_agent}</span><span>${slot.estimated_price || slot.hourly_rate} / {slot.estimated_price_unit || "hour"}</span><span>{slot.level_name} • {slot.distance_to_entrance_meters}m</span><span>{slot.ev_charger ? "EV" : ""} {slot.handicap ? "ADA" : ""}</span></button>)}</div></div><div className="card actionCard"><h2>Selected Slot</h2>{selectedSlot ? <><div className="selectedSummary"><b>{selectedSlot.slot_code}</b><span>{selectedSlot.provider_agent}</span><span>Status: {selectedSlot.status}</span><span>Level: {selectedSlot.level_name}</span><span>Price: ${selectedSlot.estimated_price || selectedSlot.hourly_rate}</span></div><button className="secondaryBtn" disabled={busy || selectedSlot.status !== "AVAILABLE"} onClick={holdSelectedSlot}>Hold</button><button className="primaryBtn" disabled={busy || selectedSlot.status !== "AVAILABLE"} onClick={reserveSelectedSlot}>Reserve Directly</button></> : <p className="muted">Select a recommended slot or a slot from layout.</p>}</div></section>
        <section className="card garageCard"><div className="garageHeader"><div><h2>{currentGarage?.name || "Garage Layout"}</h2><p>{selectedProviderAgent || "No provider selected"}</p></div><div className="levels">{levels.map((level)=><button key={level.name} className={activeLevel === level.name ? "level active" : "level"} onClick={()=>setActiveLevel(level.name)}>{level.name}</button>)}</div></div><div className="garageGrid">{currentLevel?.rows?.map((row)=><div className="garageRow" key={row.label}><div className="rowLabel">{row.label}</div><div className="slotGrid">{row.slots.map((slot)=>{const recommended=recommendedSlotCodes.has(slot.slot_code); const selected=selectedSlot?.slot_code===slot.slot_code; return <button key={slot.slot_code} className={statusClass(slot.status, selected, recommended)} onClick={()=>setSelectedSlot({...slot, provider_agent:selectedProviderAgent, provider_url: providerSummaries.find(p=>p.provider_agent===selectedProviderAgent)?.provider_url || selectedSlot?.provider_url})} title={`${slot.slot_code} ${slot.status}`}><b>{slot.column_number}</b><small>{slot.ev_charger ? "EV" : slot.handicap ? "ADA" : ""}</small></button>})}</div></div>)}</div></section>
      </main>
    </div>
  );
}

function App() {
  const [portal, setPortal] = useState(() => localStorage.getItem("parknexus_portal") || "login");
  const [user, setUser] = useState(() => JSON.parse(localStorage.getItem("parknexus_user") || "null"));
  const [admin, setAdmin] = useState(() => JSON.parse(localStorage.getItem("parknexus_admin") || "null"));

  function onUserLogin(nextUser) {
    localStorage.setItem("parknexus_user", JSON.stringify(nextUser));
    localStorage.setItem("parknexus_portal", "user");
    setUser(nextUser);
    setPortal("user");
  }
  function onAdminLogin(nextAdmin) {
    localStorage.setItem("parknexus_admin", JSON.stringify(nextAdmin));
    localStorage.setItem("parknexus_portal", "admin");
    setAdmin(nextAdmin);
    setPortal("admin");
  }
  function logout() {
    localStorage.removeItem("parknexus_user");
    localStorage.removeItem("parknexus_admin");
    localStorage.setItem("parknexus_portal", "login");
    setUser(null); setAdmin(null); setPortal("login");
  }

  if (portal === "admin" && admin) return <AdminPortal admin={admin} onLogout={logout} />;
  if (portal === "user" && user) return <UserPortal user={user} onLogout={logout} />;
  return <LoginPage onUserLogin={onUserLogin} onAdminLogin={onAdminLogin} />;
}

createRoot(document.getElementById("root")).render(<App />);
