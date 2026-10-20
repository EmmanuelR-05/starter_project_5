import { useEffect, useRef, useState } from "react";
import { api, setToken } from "./api.js";

const fmt = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

function highScore(game) {
  const top = game.leaderboard?.entries?.[0]; // backend orders: most words, then fastest
  return top
    ? `${top.words_found_count} words · ${fmt(top.total_time_seconds)} · ${top.player_name}`
    : "No scores yet";
}

function AuthPanel({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [username, setU] = useState("");
  const [password, setP] = useState("");
  const [err, setErr] = useState("");

  async function submit(e) {
    e.preventDefault();
    try {
      const d = await (mode === "login" ? api.login : api.register)(username, password);
      onAuth(d);
    } catch (x) {
      setErr(x.message);
    }
  }
  return (
    <form className="auth" onSubmit={submit}>
      <input placeholder="Username" value={username} onChange={(e) => setU(e.target.value)} />
      <input type="password" placeholder="Password (8+ chars)" value={password} onChange={(e) => setP(e.target.value)} />
      <button>{mode === "login" ? "Log in" : "Register"}</button>
      <button type="button" className="link" onClick={() => setMode(mode === "login" ? "register" : "login")}>
        {mode === "login" ? "Need an account?" : "Have an account?"}
      </button>
      {err && <p className="err">{err}</p>}
    </form>
  );
}

function ChallengeList({ games, onPick, user, onCreate, languages }) {
  const [size, setSize] = useState(4);
  const [lang, setLang] = useState("English");
  return (
    <section className="panel">
      <h2>Challenges</h2>
      {user && (
        <div className="row">
          <select value={size} onChange={(e) => setSize(+e.target.value)}>
            {[3, 4, 5, 6].map((n) => <option key={n} value={n}>{n}×{n}</option>)}
          </select>
          <select value={lang} onChange={(e) => setLang(e.target.value)}>
            {languages.map((l) => <option key={l.code}>{l.name}</option>)}
          </select>
          <button onClick={() => onCreate(size, lang)}>+ New random grid</button>
        </div>
      )}
      {games.length === 0 && <p className="muted">No challenges yet{user ? "." : " — log in to create one."}</p>}
      <ul className="challenges">
        {games.map((g) => (
          <li key={g.id}>
            <button onClick={() => onPick(g)}>
              <b>{g.name}</b>
              <span>{g.size}×{g.size} · {g.dictionary_language}</span>
              <em>🏆 {highScore(g)}</em>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function App() {
  const [user, setUser] = useState(() => JSON.parse(localStorage.getItem("user") || "null"));
  const [showAuth, setShowAuth] = useState(false);
  const [games, setGames] = useState([]);
  const [languages, setLanguages] = useState([{ code: "en", name: "English" }]);
  const [showList, setShowList] = useState(false);
  const [game, setGame] = useState(null);
  const [phase, setPhase] = useState("idle"); // idle | playing | done
  const [session, setSession] = useState(null);
  const [found, setFound] = useState([]);
  const [remaining, setRemaining] = useState([]);
  const [input, setInput] = useState("");
  const [msg, setMsg] = useState(null);
  const [seconds, setSeconds] = useState(0);
  const startedAt = useRef(0);

  useEffect(() => {
    if (phase !== "playing") return;
    const t = setInterval(() => setSeconds(Math.floor((Date.now() - startedAt.current) / 1000)), 500);
    return () => clearInterval(t);
  }, [phase]);

  const say = (text, kind = "info") => setMsg({ text, kind });
  const refresh = () => api.games().then(setGames).catch((e) => say(e.message, "bad"));

  function onAuth(d) {
    setToken(d.token);
    localStorage.setItem("user", JSON.stringify(d.user));
    setUser(d.user);
    setShowAuth(false);
  }
  async function logout() {
    try { await api.logout(); } catch { /* token may already be invalid */ }
    setToken(null);
    localStorage.removeItem("user");
    setUser(null);
  }

  async function openList() {
    setShowList((v) => !v);
    refresh();
    api.dictionaries().then(setLanguages).catch(() => {});
  }
  function pick(g) {
    setGame(g); setPhase("idle"); setFound([]); setRemaining([]); setSession(null);
    setSeconds(0); setMsg(null); setShowList(false);
  }
  async function create(size, lang) {
    try { pick(await api.createGame(size, lang)); refresh(); } catch (e) { say(e.message, "bad"); }
  }

  async function start() {
    try {
      if (user) {
        const s = await api.join(game.id);
        setSession(await api.start(s.id).then(() => s));
      }
      setFound([]); setRemaining([]); setMsg(null); setSeconds(0);
      startedAt.current = Date.now();
      setPhase("playing");
    } catch (e) {
      if (e.status === 401) await logout();
      say(e.message, "bad");
    }
  }

  async function stop() {
    let elapsed = Math.floor((Date.now() - startedAt.current) / 1000);
    try {
      if (user && session) {
        const r = await api.finish(session.id);
        elapsed = r.leaderboard_entry.total_time_seconds;
      }
      const r = await api.reveal(game.id, found);
      setRemaining(r.remaining);
      refresh();
    } catch (e) { say(e.message, "bad"); }
    setSeconds(elapsed);
    setPhase("done");
  }

  async function submit(e) {
    e.preventDefault();
    const word = input.trim().toUpperCase();
    setInput("");
    if (!word) return;
    if (found.includes(word)) return say(`You already found “${word}”.`, "warn");
    try {
      if (user) await api.submit(session.id, word);
      else if (!(await api.check(game.id, word)).valid) throw Object.assign(new Error("not a word here"), { status: 400 });
      setFound((f) => [word, ...f]);
      say(`+1 “${word}”`, "good");
    } catch (x) {
      if (x.status === 409) say(`You already found “${word}”.`, "warn");
      else say(`“${word}” isn't a valid word for this grid.`, "bad");
    }
  }

  return (
    <div className="app">
      <header>
        <h1>Boggle</h1>
        <div className="who">
          {user ? (<><span>{user.username}</span><button className="link" onClick={logout}>Log out</button></>)
                : (<><span>Playing as guest</span><button className="link" onClick={() => setShowAuth((v) => !v)}>Log in / Register</button></>)}
        </div>
      </header>
      {showAuth && !user && <AuthPanel onAuth={onAuth} />}

      <div className="bar">
        <button disabled={phase === "playing"} onClick={openList}>Load Challenge</button>
        {game && phase !== "playing" && <button className="go" onClick={start}>{phase === "done" ? "Play again" : "Start"}</button>}
        {phase === "playing" && <button className="stop" onClick={stop}>Stop</button>}
        {game && <span className="timer">⏱ {fmt(seconds)}</span>}
      </div>

      {showList && <ChallengeList games={games} onPick={pick} user={user} onCreate={create} languages={languages} />}
      {!game && <p className="muted">Load a challenge to begin.</p>}

      {game && (
        <main>
          <div>
            <h2>{game.name}</h2>
            {phase === "idle" ? (
              <div className="hidden-board">Board hidden — press Start</div>
            ) : (
              <div className="board" style={{ gridTemplateColumns: `repeat(${game.size}, 1fr)` }}>
                {game.grid.flat().map((c, i) => <div key={i} className="tile">{c}</div>)}
              </div>
            )}
            {phase === "playing" && (
              <form className="row" onSubmit={submit}>
                <input autoFocus value={input} onChange={(e) => setInput(e.target.value)} placeholder="Type a word" />
                <button>Submit</button>
              </form>
            )}
            {msg && <p className={`msg ${msg.kind}`}>{msg.text}</p>}
            {phase === "done" && <p className="msg info">Game over — {found.length} found in {fmt(seconds)}.</p>}
          </div>
          <aside>
            <h3>Found ({found.length})</h3>
            <ul className="words">{found.map((w) => <li key={w}>{w}</li>)}</ul>
            {phase === "done" && (
              <>
                <h3>Remaining ({remaining.length})</h3>
                <ul className="words missed">{remaining.map((w) => <li key={w}>{w}</li>)}</ul>
              </>
            )}
          </aside>
        </main>
      )}
    </div>
  );
}
