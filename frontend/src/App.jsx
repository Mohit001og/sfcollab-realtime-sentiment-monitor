import { Component, useEffect, useMemo, useRef, useState } from 'react';
import { backendConfig } from './services/backendConfig';

const MESSAGE_LIMIT = 50;
const MOOD_WINDOW_MINUTES = 60;
const CHART_WIDTH = 1000;
const CHART_HEIGHT = 240;
const CHART_PADDING = 28;

function formatMoodScore(score) {
  if (score === null || score === undefined) {
    return 'No messages in the last 60 minutes';
  }

  return `${score > 0 ? '+' : ''}${score.toFixed(2)}`;
}

function moodTone(score) {
  if (score === null || score === undefined) return 'neutral';
  if (score > 0.15) return 'positive';
  if (score < -0.15) return 'negative';
  return 'mixed';
}

function isMessageEvent(payload) {
  return (
    payload &&
    payload.type === 'message' &&
    payload.data &&
    typeof payload.data.message === 'string' &&
    typeof payload.data.sentiment === 'string' &&
    typeof payload.data.score === 'number' &&
    typeof payload.data.latency_ms === 'number' &&
    typeof payload.data.timestamp === 'string' &&
    payload.mood &&
    'score' in payload.mood &&
    typeof payload.mood.window_minutes === 'number' &&
    typeof payload.mood.message_count === 'number'
  );
}

function toDisplayTimestamp(value) {
  if (typeof value !== 'string') return 'Invalid timestamp';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'Invalid timestamp';
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsed);
}

function toChartLabel(value) {
  if (typeof value !== 'string') return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '';
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  }).format(parsed);
}

function sentimentClass(sentiment) {
  if (sentiment === 'POSITIVE') return 'sentiment-pill sentiment-positive';
  if (sentiment === 'NEGATIVE') return 'sentiment-pill sentiment-negative';
  return 'sentiment-pill sentiment-neutral';
}

function normalizeMood(data) {
  if (!data || typeof data !== 'object') {
    return {
      score: null,
      windowMinutes: MOOD_WINDOW_MINUTES,
      messageCount: 0,
      history: [],
    };
  }

  const score = typeof data.score === 'number' && Number.isFinite(data.score) ? data.score : null;
  const windowMinutes =
    typeof data.window_minutes === 'number' && Number.isFinite(data.window_minutes)
      ? data.window_minutes
      : MOOD_WINDOW_MINUTES;
  const messageCount =
    typeof data.message_count === 'number' && Number.isFinite(data.message_count)
      ? data.message_count
      : 0;

  return {
    score,
    windowMinutes,
    messageCount,
    history: Array.isArray(data.history)
      ? data.history
          .filter((item) => item && typeof item.timestamp === 'string' && typeof item.score === 'number' && Number.isFinite(item.score))
          .map((item) => ({ timestamp: item.timestamp, score: item.score }))
      : [],
  };
}

function parseTimestamp(value) {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function signedPointFromMessage(message) {
  if (!message || typeof message !== 'object') return null;
  if (typeof message.timestamp !== 'string' || typeof message.sentiment !== 'string' || typeof message.score !== 'number') {
    return null;
  }

  const timestamp = parseTimestamp(message.timestamp);
  if (!timestamp) return null;

  const signedScore = message.sentiment === 'NEGATIVE' ? -Math.abs(message.score) : Math.abs(message.score);
  return {
    timestamp: message.timestamp,
    score: signedScore,
    timestampMs: timestamp.getTime(),
  };
}

function normalizeHistory(history) {
  return Array.isArray(history)
    ? history
        .map((item) => {
          if (!item || typeof item.timestamp !== 'string' || typeof item.score !== 'number') return null;
          const timestamp = parseTimestamp(item.timestamp);
          if (!timestamp) return null;
          return {
            timestamp: item.timestamp,
            score: item.score,
            timestampMs: timestamp.getTime(),
          };
        })
        .filter(Boolean)
    : [];
}

function dedupeHistory(points) {
  const seen = new Set();
  return points.filter((point) => {
    const key = `${point.timestamp}|${point.score}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function pruneChartHistory(points, latestTimestampMs, windowMinutes = MOOD_WINDOW_MINUTES) {
  if (!points.length || !Number.isFinite(latestTimestampMs)) return points.slice();
  const cutoff = latestTimestampMs - windowMinutes * 60 * 1000;
  return points.filter((point) => point.timestampMs > cutoff).slice(-MESSAGE_LIMIT);
}

function getChartFrame(points) {
  if (!points.length) {
    return null;
  }

  const sorted = [...points].sort((a, b) => a.timestampMs - b.timestampMs);
  const latest = sorted[sorted.length - 1];
  const earliestWindow = latest.timestampMs - MOOD_WINDOW_MINUTES * 60 * 1000;
  const minX = Math.min(earliestWindow, sorted[0].timestampMs);
  const maxX = latest.timestampMs;
  return { points: sorted, minX, maxX };
}

function buildChartPath(points, width, height, padding) {
  if (points.length === 0) return '';

  const usableWidth = Math.max(1, width - padding * 2);
  const usableHeight = Math.max(1, height - padding * 2);
  const frame = getChartFrame(points);
  if (!frame) return '';

  const { points: sorted, minX, maxX } = frame;
  const xSpan = Math.max(1, maxX - minX);
  const yMin = -1;
  const yMax = 1;
  const ySpan = yMax - yMin;

  return sorted
    .map((point, index) => {
      const xRatio = (point.timestampMs - minX) / xSpan;
      const clampedX = Number.isFinite(xRatio) ? Math.min(1, Math.max(0, xRatio)) : 0;
      const yRatio = (point.score - yMin) / ySpan;
      const clampedY = Number.isFinite(yRatio) ? Math.min(1, Math.max(0, yRatio)) : 0.5;
      const x = padding + clampedX * usableWidth;
      const y = padding + (1 - clampedY) * usableHeight;
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(' ');
}

function getChartPoints(points, width, height, padding) {
  if (!points.length) return [];
  const usableWidth = Math.max(1, width - padding * 2);
  const usableHeight = Math.max(1, height - padding * 2);
  const frame = getChartFrame(points);
  if (!frame) return [];

  const { points: sorted, minX, maxX } = frame;
  const xSpan = Math.max(1, maxX - minX);
  const yMin = -1;
  const yMax = 1;
  const ySpan = yMax - yMin;

  return sorted.map((point) => {
    const xRatio = (point.timestampMs - minX) / xSpan;
    const clampedX = Number.isFinite(xRatio) ? Math.min(1, Math.max(0, xRatio)) : 0;
    const yRatio = (point.score - yMin) / ySpan;
    const clampedY = Number.isFinite(yRatio) ? Math.min(1, Math.max(0, yRatio)) : 0.5;
    return {
      ...point,
      x: padding + clampedX * usableWidth,
      y: padding + (1 - clampedY) * usableHeight,
    };
  });
}

function ChartLegend() {
  return (
    <div className="chart-legend" aria-label="Mood legend">
      <span><i className="legend-swatch positive" />Positive</span>
      <span><i className="legend-swatch neutral" />Neutral</span>
      <span><i className="legend-swatch negative" />Negative</span>
    </div>
  );
}

function MoodChart({ history, windowMinutes }) {
  const validHistory = useMemo(() => normalizeHistory(history), [history]);
  const frame = useMemo(() => getChartFrame(validHistory), [validHistory]);

  if (!validHistory.length) {
    return (
      <div className="chart-empty">
        <p>No mood activity in the last 60 minutes.</p>
        <p>The chart will appear once team messages start flowing.</p>
      </div>
    );
  }

  const path = buildChartPath(validHistory, CHART_WIDTH, CHART_HEIGHT, CHART_PADDING);
  const points = getChartPoints(validHistory, CHART_WIDTH, CHART_HEIGHT, CHART_PADDING);
  const zeroY = CHART_PADDING + (CHART_HEIGHT - CHART_PADDING * 2) / 2;
  const firstPoint = points[0];
  const lastPoint = points[points.length - 1];
  const labels = frame
    ? [
        { x: CHART_PADDING, text: toChartLabel(frame.points[0].timestamp) },
        { x: (CHART_WIDTH / 2), text: toChartLabel(frame.points[Math.floor(frame.points.length / 2)].timestamp) },
        { x: CHART_WIDTH - CHART_PADDING, text: toChartLabel(frame.points[frame.points.length - 1].timestamp) },
      ]
    : [];

  return (
    <div className="mood-chart-wrap">
      <svg viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} className="mood-chart" role="img" aria-label="60-minute mood chart">
        <defs>
          <linearGradient id="positiveFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(82, 204, 138, 0.22)" />
            <stop offset="100%" stopColor="rgba(82, 204, 138, 0.03)" />
          </linearGradient>
          <linearGradient id="negativeFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(233, 93, 93, 0.22)" />
            <stop offset="100%" stopColor="rgba(233, 93, 93, 0.03)" />
          </linearGradient>
        </defs>

        <line x1={CHART_PADDING} y1={zeroY} x2={CHART_WIDTH - CHART_PADDING} y2={zeroY} className="chart-zero-line" />
        <line x1={CHART_PADDING} y1={CHART_PADDING} x2={CHART_PADDING} y2={CHART_HEIGHT - CHART_PADDING} className="chart-axis" />
        <line x1={CHART_PADDING} y1={CHART_HEIGHT - CHART_PADDING} x2={CHART_WIDTH - CHART_PADDING} y2={CHART_HEIGHT - CHART_PADDING} className="chart-axis" />

        <path d={path} className="chart-line" />

        {points.length > 1 && (
          <path
            d={`${path} L ${points[points.length - 1].x.toFixed(2)} ${zeroY.toFixed(2)} L ${points[0].x.toFixed(2)} ${zeroY.toFixed(2)} Z`}
            className={`chart-fill chart-fill-${moodTone(points[points.length - 1].score)}`}
          />
        )}

        {points.map((point, index) => (
          <circle
            key={`${point.timestamp}-${point.score}`}
            cx={point.x}
            cy={point.y}
            r={index === points.length - 1 ? 5 : 4}
            className={`chart-point ${point.score >= 0 ? 'positive' : 'negative'}`}
          />
        ))}

        {labels.map((label) => (
          <text key={`${label.x}-${label.text}`} x={label.x} y={CHART_HEIGHT - 8} textAnchor="middle" className="chart-label">
            {label.text}
          </text>
        ))}
      </svg>

      <div className="chart-note">
        <span>Signed mood values plotted from backend history.</span>
        <span>Window: {windowMinutes} minutes</span>
        {lastPoint ? <span>Latest point: {toDisplayTimestamp(lastPoint.timestamp)}</span> : null}
        {firstPoint && points.length === 1 ? <span>Single-point trend. More messages will create a line.</span> : null}
      </div>
    </div>
  );
}

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="dashboard-shell">
          <section className="dashboard">
            <div className="alert-strip" role="alert">
              The dashboard could not render this state. Refresh the page or check the backend configuration.
            </div>
          </section>
        </main>
      );
    }

    return this.props.children;
  }
}

function Dashboard() {
  const [messages, setMessages] = useState([]);
  const [mood, setMood] = useState(() => normalizeMood(null));
  const [moodLoading, setMoodLoading] = useState(true);
  const [moodError, setMoodError] = useState('');
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [connectionError, setConnectionError] = useState('');
  const [sendStatus, setSendStatus] = useState('idle');
  const [sendError, setSendError] = useState('');
  const [draft, setDraft] = useState('');
  const [chartHistory, setChartHistory] = useState([]);
  const reconnectTimerRef = useRef(null);
  const socketRef = useRef(null);
  const mountedRef = useRef(true);
  const reconnectAttemptsRef = useRef(0);

  const moodToneClass = useMemo(() => moodTone(mood?.score ?? null), [mood?.score]);
  const trimmedDraft = draft.trim();
  const canSubmit = sendStatus !== 'sending' && trimmedDraft.length > 0 && trimmedDraft.length <= 1000;

  function replaceChartHistory(nextHistory, latestTimestampMs) {
    const normalized = dedupeHistory(nextHistory);
    const pruned = pruneChartHistory(normalized, latestTimestampMs, MOOD_WINDOW_MINUTES);
    setChartHistory(pruned);
  }

  function appendChartPoint(point) {
    if (!point) return;
    setChartHistory((current) => {
      const merged = dedupeHistory([...current, point]);
      return pruneChartHistory(merged, point.timestampMs, MOOD_WINDOW_MINUTES);
    });
  }

  useEffect(() => {
    mountedRef.current = true;
    let active = true;

    async function loadMood() {
      setMoodLoading(true);
      setMoodError('');
      try {
        const response = await fetch(`${backendConfig.httpBaseUrl}/mood`);
        if (!response.ok) {
          throw new Error(`GET /mood failed with status ${response.status}`);
        }
        const data = await response.json();
        if (!active) return;
        const normalized = normalizeMood(data);
        setMood(normalized);
        const initialHistory = normalizeHistory(normalized?.history);
        const latestTimestampMs = initialHistory.length ? initialHistory[initialHistory.length - 1].timestampMs : Date.now();
        replaceChartHistory(initialHistory, latestTimestampMs);
      } catch (error) {
        if (!active) return;
        setMoodError(error instanceof Error ? error.message : 'Failed to load mood state');
        setMood(normalizeMood(null));
        setChartHistory([]);
      } finally {
        if (active) setMoodLoading(false);
      }
    }

    loadMood();

    return () => {
      active = false;
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const clearReconnectTimer = () => {
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    const connect = () => {
      if (cancelled || !mountedRef.current) return;
      clearReconnectTimer();

      setConnectionStatus((current) => (current === 'connected' ? 'connected' : 'connecting'));
      setConnectionError('');

      let socket;
      try {
        socket = new WebSocket(backendConfig.wsUrl);
      } catch (error) {
        setConnectionStatus('error');
        setConnectionError(error instanceof Error ? error.message : 'WebSocket connection error');
        return;
      }
      socketRef.current = socket;

      socket.onopen = () => {
        if (!mountedRef.current) return;
        reconnectAttemptsRef.current = 0;
        setConnectionStatus('connected');
        setConnectionError('');
      };

      socket.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const payload = JSON.parse(event.data);
          if (!isMessageEvent(payload)) {
            return;
          }

          const nextMessage = {
            message: payload.data.message,
            sentiment: payload.data.sentiment,
            score: payload.data.score,
            latencyMs: payload.data.latency_ms,
            timestamp: payload.data.timestamp,
          };

          setMessages((current) => [nextMessage, ...current].slice(0, MESSAGE_LIMIT));
          setMood(normalizeMood(payload.mood));

          const point = signedPointFromMessage(payload.data);
          if (point) {
            appendChartPoint(point);
          }
        } catch (error) {
          setConnectionError('Received malformed WebSocket data');
        }
      };

      socket.onerror = () => {
        if (!mountedRef.current) return;
        setConnectionStatus('error');
        setConnectionError('WebSocket connection error');
      };

      socket.onclose = () => {
        if (!mountedRef.current || cancelled) return;
        setConnectionStatus((current) => (current === 'connected' ? 'disconnected' : current));
        if (reconnectAttemptsRef.current < 5) {
          reconnectAttemptsRef.current += 1;
          setConnectionStatus('reconnecting');
          reconnectTimerRef.current = window.setTimeout(connect, 1200);
        }
      };
    };

    connect();

    return () => {
      cancelled = true;
      clearReconnectTimer();
      socketRef.current?.close();
    };
  }, []);

  const moodScore = mood?.score;
  const moodMessageCount = mood?.messageCount ?? 0;
  const moodWindowMinutes = mood?.windowMinutes ?? MOOD_WINDOW_MINUTES;
  const moodHistory = mood?.history ?? [];
  const moodLabel = typeof moodScore === 'number' ? formatMoodScore(moodScore) : 'No active mood';

  async function handleSubmit(event) {
    event.preventDefault();
    setSendError('');

    const value = trimmedDraft;
    if (!value) {
      setSendError('Please enter a non-empty message.');
      return;
    }

    if (value.length > 1000) {
      setSendError('Message must be 1000 characters or fewer.');
      return;
    }

    setSendStatus('sending');
    try {
      const response = await fetch(`${backendConfig.httpBaseUrl}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: value }),
      });

      if (!response.ok) {
        let message = `POST /messages failed with status ${response.status}`;
        try {
          const errorBody = await response.json();
          if (errorBody?.detail) {
            message = Array.isArray(errorBody.detail)
              ? errorBody.detail.map((item) => item?.msg ?? item).join(', ')
              : errorBody.detail;
          }
        } catch {
          // Ignore JSON parse failures and keep the generic message.
        }
        throw new Error(message);
      }

      setDraft('');
      setSendStatus('sent');
      window.setTimeout(() => {
        if (mountedRef.current) setSendStatus('idle');
      }, 1200);
    } catch (error) {
      setSendStatus('error');
      setSendError(error instanceof Error ? error.message : 'Failed to send message');
    }
  }

  return (
    <main className="dashboard-shell">
      <section className="dashboard">
        <header className="header-card">
          <div>
            <p className="eyebrow">SFCollab</p>
            <h1>Real-Time Sentiment Monitor</h1>
            <p className="subtitle">Live team sentiment and mood monitoring</p>
          </div>

          <div className={`status-badge status-${connectionStatus}`} aria-live="polite">
            <span className="status-dot" />
            <span>{connectionStatus === 'error' ? 'Error' : connectionStatus[0].toUpperCase() + connectionStatus.slice(1)}</span>
          </div>
        </header>

        {(moodError || connectionError) && (
          <div className="alert-strip" role="alert">
            {moodError || connectionError}
          </div>
        )}

        <section className={`mood-card mood-${moodToneClass}`}>
          <div className="card-heading">
            <div>
              <p className="card-kicker">Current team mood</p>
              <h2>{moodLoading ? 'Loading mood state...' : moodLabel}</h2>
            </div>
            <div className="window-chip">Last 60 minutes</div>
          </div>

          <div className="mood-metrics">
            <div className="metric-block">
              <span className="metric-label">Mood score</span>
              <strong className="metric-value">
                {moodLoading ? '-' : typeof moodScore === 'number' ? moodScore.toFixed(2) : 'No messages in the last 60 minutes'}
              </strong>
            </div>
            <div className="metric-block">
              <span className="metric-label">Message count</span>
              <strong className="metric-value">{moodLoading ? '-' : moodMessageCount}</strong>
            </div>
            <div className="metric-block">
              <span className="metric-label">Window</span>
              <strong className="metric-value">60 minutes</strong>
            </div>
          </div>

          {moodHistory.length ? (
            <div className="history-summary">
              <span className="metric-label">History available for the active window</span>
              <div className="history-line">
                {moodHistory.slice(-4).map((item) => (
                  <span key={`${item.timestamp}-${item.score}`} className={item.score >= 0 ? 'history-token positive' : 'history-token negative'}>
                    {item.score >= 0 ? '+' : ''}
                    {item.score.toFixed(2)}
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <p className="empty-copy">No messages in the last 60 minutes.</p>
          )}
        </section>

        <section className="chart-panel panel">
          <div className="card-heading compact">
            <div>
              <p className="card-kicker">60-minute mood</p>
              <h2>Mood over time</h2>
            </div>
            <div className="panel-meta">{moodWindowMinutes} minute window</div>
          </div>
          <ChartLegend />
          <MoodChart history={chartHistory} windowMinutes={moodWindowMinutes} />
        </section>

        <section className="content-grid">
          <section className="panel feed-panel">
            <div className="card-heading compact">
              <div>
                <p className="card-kicker">Live message feed</p>
                <h2>Recent messages</h2>
              </div>
              <div className="panel-meta">{messages.length} shown</div>
            </div>

            {messages.length ? (
              <ul className="message-list">
                {messages.map((item) => (
                  <li key={`${item.timestamp}-${item.message}`} className="message-item">
                    <div className="message-row">
                      <p className="message-text">{item.message}</p>
                      <span className={sentimentClass(item.sentiment)}>{item.sentiment}</span>
                    </div>
                    <div className="message-meta">
                      <span>{toDisplayTimestamp(item.timestamp)}</span>
                      <span>Score {item.score.toFixed(2)}</span>
                      <span>{item.latencyMs.toFixed(1)} ms</span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="empty-state">
                <p>No live messages yet.</p>
                <p>Send a message or wait for WebSocket activity to populate the feed.</p>
              </div>
            )}
          </section>

          <section className="panel compose-panel">
            <div className="card-heading compact">
              <div>
                <p className="card-kicker">Send message</p>
                <h2>Post to the backend</h2>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="compose-form">
              <label className="field-label" htmlFor="message">
                Team message
              </label>
              <textarea
                id="message"
                name="message"
                rows="5"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="Type a team message..."
                maxLength={1000}
                aria-invalid={Boolean(sendError)}
                aria-describedby="message-help message-error"
              />
              <div className="form-row">
                <span className="helper-text" id="message-help">
                  {trimmedDraft.length}/1000
                </span>
                <button type="submit" disabled={!canSubmit}>
                  {sendStatus === 'sending' ? 'Sending...' : 'Send message'}
                </button>
              </div>
              <p className="form-status" id="message-error" aria-live="polite">
                {sendError || (sendStatus === 'sent' ? 'Message sent successfully.' : 'Messages are posted to the backend and broadcast to connected clients.')}
              </p>
            </form>
          </section>
        </section>
      </section>
    </main>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <Dashboard />
    </ErrorBoundary>
  );
}
