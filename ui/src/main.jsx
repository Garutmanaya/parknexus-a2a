import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const HOST_URL = import.meta.env.VITE_HOST_AGENT_URL || "https://localhost:8030";
const DEFAULT_USER = import.meta.env.VITE_PARKNEXUS_USER || "ui_user_001";

async function apiPost(path, body) {
  const response = await fetch(`${HOST_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const payload = await response.json();

  if (!response.ok) {
    throw new Error(payload.detail || JSON.stringify(payload));
  }

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

function providerLabel(slot) {
  return slot.provider_name || slot.provider_agent || "Provider";
}

function App() {
  const [message, setMessage] = useState("Find me cheap EV parking under $20 per day");
  const [conversation, setConversation] = useState([]);
  const [searchResult, setSearchResult] = useState(null);
  const [layout, setLayout] = useState(null);
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [selectedProviderAgent, setSelectedProviderAgent] = useState(null);
  const [activeLevel, setActiveLevel] = useState("");
  const [transactions, setTransactions] = useState([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Ready");

  const recommendedSlotCodes = useMemo(() => {
    const values = new Set();
    for (const slot of searchResult?.slots || []) {
      if (!selectedProviderAgent || slot.provider_agent === selectedProviderAgent) {
        values.add(slot.slot_code);
      }
    }
    return values;
  }, [searchResult, selectedProviderAgent]);

  const providerSummaries = useMemo(() => {
    const map = new Map();

    for (const slot of searchResult?.slots || []) {
      const key = slot.provider_agent;
      const current = map.get(key) || {
        provider_agent: key,
        provider_url: slot.provider_url,
        count: 0,
        min_price: null,
        nearest_distance: null,
      };

      const price = Number(slot.estimated_price || slot.hourly_rate || slot.price_per_hour || 0);
      current.count += 1;
      current.min_price = current.min_price === null ? price : Math.min(current.min_price, price);
      current.nearest_distance =
        current.nearest_distance === null
          ? slot.distance_to_entrance_meters
          : Math.min(current.nearest_distance, slot.distance_to_entrance_meters);

      map.set(key, current);
    }

    return Array.from(map.values());
  }, [searchResult]);

  const currentGarage = layout?.garages?.[0];
  const levels = currentGarage?.levels || [];
  const currentLevel = levels.find((level) => level.name === activeLevel) || levels[0];

  function addConversation(role, text) {
    setConversation((previous) => [{ role, text, time: new Date().toLocaleTimeString() }, ...previous].slice(0, 20));
  }

  function addTransaction(transaction) {
    setTransactions((previous) => [
      { ...transaction, time: new Date().toLocaleTimeString() },
      ...previous,
    ].slice(0, 5));
  }

  async function askHostAgent() {
    if (!message.trim()) return;

    setBusy(true);
    setStatus("Searching through Host Agent...");
    addConversation("user", message);

    try {
      const result = await apiPost("/parking/chat", { message });
      setSearchResult(result);

      const firstSlot = result.slots?.[0];
      if (firstSlot) {
        setSelectedProviderAgent(firstSlot.provider_agent);
        setSelectedSlot(firstSlot);
        await loadGarageLayout(firstSlot.provider_agent);
      }

      addConversation("agent", `Found ${result.count || 0} matching slots.`);
      setStatus(`Search completed: ${result.count || 0} slots`);
    } catch (error) {
      addConversation("agent", `Search failed: ${error.message}`);
      setStatus(`Search failed: ${error.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function loadGarageLayout(providerAgent) {
    if (!providerAgent) return;

    const data = await apiPost("/garage/layout", { provider_agent: providerAgent });
    setLayout(data);

    const firstLevel = data.garages?.[0]?.levels?.[0]?.name || "";
    setActiveLevel(firstLevel);
  }

  async function selectProvider(providerAgent) {
    setSelectedProviderAgent(providerAgent);
    setSelectedSlot(null);
    setStatus(`Loading layout for ${providerAgent}...`);

    try {
      await loadGarageLayout(providerAgent);
      setStatus(`Loaded layout for ${providerAgent}`);
    } catch (error) {
      setStatus(`Layout failed: ${error.message}`);
    }
  }

  async function holdSelectedSlot() {
    if (!selectedSlot) return;

    setBusy(true);
    setStatus(`Holding ${selectedSlot.slot_code}...`);

    try {
      const result = await apiPost("/parking/hold", {
        provider_url: selectedSlot.provider_url,
        slot_code: selectedSlot.slot_code,
        user_id: DEFAULT_USER,
        hold_minutes: 5,
      });

      addTransaction({
        type: "HOLD",
        provider_agent: selectedSlot.provider_agent,
        provider_url: selectedSlot.provider_url,
        slot_code: selectedSlot.slot_code,
        hold_id: result.hold_id,
        status: "HELD",
      });

      addConversation("agent", `Held ${selectedSlot.slot_code}. Hold ID: ${result.hold_id}`);
      setStatus(`Held ${selectedSlot.slot_code}`);
      await loadGarageLayout(selectedSlot.provider_agent);
    } catch (error) {
      setStatus(`Hold failed: ${error.message}`);
      addConversation("agent", `Hold failed: ${error.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function reserveSelectedSlot() {
    if (!selectedSlot) return;

    setBusy(true);
    setStatus(`Holding and confirming ${selectedSlot.slot_code}...`);

    try {
      const hold = await apiPost("/parking/hold", {
        provider_url: selectedSlot.provider_url,
        slot_code: selectedSlot.slot_code,
        user_id: DEFAULT_USER,
        hold_minutes: 5,
      });

      const reservation = await apiPost("/parking/confirm", {
        provider_url: selectedSlot.provider_url,
        hold_id: hold.hold_id,
        user_id: DEFAULT_USER,
        reserved_minutes: 120,
      });

      addTransaction({
        type: "RESERVATION",
        provider_agent: selectedSlot.provider_agent,
        provider_url: selectedSlot.provider_url,
        slot_code: selectedSlot.slot_code,
        hold_id: hold.hold_id,
        reservation_id: reservation.reservation_id,
        status: "RESERVED",
      });

      addConversation(
        "agent",
        `Reserved ${selectedSlot.slot_code}. Reservation ID: ${reservation.reservation_id}`
      );
      setStatus(`Reserved ${selectedSlot.slot_code}`);
      await loadGarageLayout(selectedSlot.provider_agent);
    } catch (error) {
      setStatus(`Reservation failed: ${error.message}`);
      addConversation("agent", `Reservation failed: ${error.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function cancelTransaction(transaction) {
    setBusy(true);

    try {
      if (transaction.hold_id && transaction.status === "HELD") {
        await apiPost("/parking/hold/cancel", {
          provider_url: transaction.provider_url,
          hold_id: transaction.hold_id,
          user_id: DEFAULT_USER,
        });

        addConversation("agent", `Cancelled hold ${transaction.hold_id}`);
      } else {
        await apiPost("/parking/release", {
          provider_url: transaction.provider_url,
          slot_code: transaction.slot_code,
          user_id: DEFAULT_USER,
          reason: "Cancelled from UI history",
        });

        addConversation("agent", `Released ${transaction.slot_code}`);
      }

      setTransactions((previous) =>
        previous.map((item) =>
          item === transaction ? { ...item, status: "CANCELLED" } : item
        )
      );

      setStatus("Cancellation completed");
      await loadGarageLayout(transaction.provider_agent);
    } catch (error) {
      setStatus(`Cancel failed: ${error.message}`);
      addConversation("agent", `Cancel failed: ${error.message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="appShell">
      <aside className="leftPane">
        <div className="brand">
          <div>
            <h1>ParkNexus A2A</h1>
            <p>Agentic parking reservation console</p>
          </div>
          <span className={busy ? "badge busy" : "badge"}>{busy ? "Working" : "Online"}</span>
        </div>

        <section className="card askCard">
          <h2>Ask Host Agent</h2>
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Find me cheap EV parking near entrance under $20 per day"
          />
          <button className="primaryBtn" onClick={askHostAgent} disabled={busy}>
            Ask
          </button>
        </section>

        <section className="card">
          <h2>Conversation</h2>
          <div className="conversation">
            {conversation.length === 0 && <p className="muted">No messages yet.</p>}
            {conversation.map((item, index) => (
              <div key={index} className={`message ${item.role}`}>
                <span>{item.time}</span>
                <p>{item.text}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="card">
          <h2>Last 5 Transactions</h2>
          <div className="history">
            {transactions.length === 0 && <p className="muted">No transactions yet.</p>}
            {transactions.map((item, index) => (
              <div className="historyItem" key={index}>
                <b>{item.type}</b>
                <span>{item.slot_code}</span>
                <small>{item.status} • {item.time}</small>
                {item.hold_id && <small>Hold: {item.hold_id}</small>}
                {item.reservation_id && <small>Reservation: {item.reservation_id}</small>}
                {item.status !== "CANCELLED" && (
                  <button onClick={() => cancelTransaction(item)} disabled={busy}>
                    Cancel / Release
                  </button>
                )}
              </div>
            ))}
          </div>
        </section>
      </aside>

      <main className="rightPane">
        <div className="topStatus">
          <span>{status}</span>
          <span>User: {DEFAULT_USER}</span>
        </div>

        <section className="providerGrid">
          {providerSummaries.length === 0 && (
            <div className="emptyState">
              Ask a question to discover providers and available slots.
            </div>
          )}

          {providerSummaries.map((provider) => (
            <button
              key={provider.provider_agent}
              className={
                selectedProviderAgent === provider.provider_agent
                  ? "providerCard active"
                  : "providerCard"
              }
              onClick={() => selectProvider(provider.provider_agent)}
            >
              <b>{provider.provider_agent}</b>
              <span>{provider.count} matching slots</span>
              <span>from ${provider.min_price}</span>
              <span>{provider.nearest_distance}m nearest</span>
            </button>
          ))}
        </section>

        <section className="contentGrid">
          <div className="card resultsCard">
            <h2>Recommended Slots</h2>
            <div className="recommendations">
              {(searchResult?.slots || []).slice(0, 10).map((slot) => (
                <button
                  className={
                    selectedSlot?.slot_code === slot.slot_code
                      ? "recommendation selectedRecommendation"
                      : "recommendation"
                  }
                  key={`${slot.provider_agent}-${slot.slot_code}`}
                  onClick={() => {
                    setSelectedSlot(slot);
                    setSelectedProviderAgent(slot.provider_agent);
                    loadGarageLayout(slot.provider_agent).catch((error) =>
                      setStatus(`Layout failed: ${error.message}`)
                    );
                  }}
                >
                  <b>{slot.slot_code}</b>
                  <span>{providerLabel(slot)}</span>
                  <span>
                    ${slot.estimated_price || slot.hourly_rate || slot.price_per_hour} /{" "}
                    {slot.estimated_price_unit || "hour"}
                  </span>
                  <span>{slot.level_name} • {slot.distance_to_entrance_meters}m</span>
                  <span>{slot.ev_charger ? "EV" : ""} {slot.handicap ? "ADA" : ""}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="card actionCard">
            <h2>Selected Slot</h2>
            {selectedSlot ? (
              <>
                <div className="selectedSummary">
                  <b>{selectedSlot.slot_code}</b>
                  <span>{selectedSlot.provider_agent}</span>
                  <span>Status: {selectedSlot.status}</span>
                  <span>Level: {selectedSlot.level_name}</span>
                  <span>
                    Price: ${selectedSlot.estimated_price || selectedSlot.hourly_rate || selectedSlot.price_per_hour}
                  </span>
                </div>
                <button
                  className="secondaryBtn"
                  disabled={busy || selectedSlot.status !== "AVAILABLE"}
                  onClick={holdSelectedSlot}
                >
                  Hold
                </button>
                <button
                  className="primaryBtn"
                  disabled={busy || selectedSlot.status !== "AVAILABLE"}
                  onClick={reserveSelectedSlot}
                >
                  Reserve Directly
                </button>
              </>
            ) : (
              <p className="muted">Select a recommended slot or a slot from the layout.</p>
            )}
          </div>
        </section>

        <section className="card garageCard">
          <div className="garageHeader">
            <div>
              <h2>{currentGarage?.name || "Garage Layout"}</h2>
              <p>{selectedProviderAgent || "No provider selected"}</p>
            </div>

            <div className="levels">
              {levels.map((level) => (
                <button
                  key={level.name}
                  className={activeLevel === level.name ? "level active" : "level"}
                  onClick={() => setActiveLevel(level.name)}
                >
                  {level.name}
                </button>
              ))}
            </div>
          </div>

          <div className="legend">
            <span><i className="availableBox" />Available</span>
            <span><i className="heldBox" />Held</span>
            <span><i className="reservedBox" />Reserved</span>
            <span><i className="recommendedBox" />Recommended</span>
            <span><i className="selectedBox" />Selected</span>
          </div>

          <div className="garageGrid">
            {currentLevel?.rows?.map((row) => (
              <div className="garageRow" key={row.label}>
                <div className="rowLabel">{row.label}</div>
                <div className="slotGrid">
                  {row.slots.map((slot) => {
                    const recommended = recommendedSlotCodes.has(slot.slot_code);
                    const selected = selectedSlot?.slot_code === slot.slot_code;
                    return (
                      <button
                        key={slot.slot_code}
                        className={statusClass(slot.status, selected, recommended)}
                        onClick={() => {
                          setSelectedSlot({
                            ...slot,
                            provider_agent: selectedProviderAgent,
                            provider_url:
                              providerSummaries.find(
                                (p) => p.provider_agent === selectedProviderAgent
                              )?.provider_url || selectedSlot?.provider_url,
                          });
                        }}
                        title={`${slot.slot_code} ${slot.status}`}
                      >
                        <b>{slot.column_number}</b>
                        <small>{slot.ev_charger ? "EV" : slot.handicap ? "ADA" : ""}</small>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);