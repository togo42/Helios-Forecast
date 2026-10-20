// Minimal read-only Recorder client using Node's built-in WebSocket (Node 22+).
export function haCall(message) {
  const endpoint = process.env.HA_URL;
  const token = process.env.HA_TOKEN;
  if (!endpoint || !token) return Promise.reject(new Error("HA_URL and HA_TOKEN are required"));
  const url = new URL(endpoint);
  if (!["https:", "http:", "wss:", "ws:"].includes(url.protocol) || url.username || url.password) {
    return Promise.reject(new Error("HA_URL must be an HTTP(S) or WS(S) origin without credentials"));
  }
  url.protocol = ["https:", "wss:"].includes(url.protocol) ? "wss:" : "ws:";
  url.pathname = "/api/websocket";
  url.search = "";
  url.hash = "";
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url);
    const timer = setTimeout(() => { reject(new Error("Recorder websocket timeout")); ws.close(); }, 60000);
    const finish = (error, result) => {
      clearTimeout(timer);
      if (error) reject(error); else resolve(result);
      ws.close();
    };
    ws.onmessage = (ev) => {
      try {
        const m = JSON.parse(ev.data);
        if (m.type === "auth_required") ws.send(JSON.stringify({ type: "auth", access_token: token }));
        else if (m.type === "auth_ok") ws.send(JSON.stringify({ id: 1, ...message }));
        else if (m.type === "auth_invalid") finish(new Error("authentication rejected"));
        else if (m.type === "result" && m.id === 1) {
          if (m.success) finish(null, m.result); else finish(new Error("Recorder request rejected"));
        }
      } catch { finish(new Error("invalid Recorder websocket response")); }
    };
    ws.onerror = () => finish(new Error("Recorder websocket error"));
    ws.onclose = () => { clearTimeout(timer); reject(new Error("Recorder websocket closed")); };
  });
}
