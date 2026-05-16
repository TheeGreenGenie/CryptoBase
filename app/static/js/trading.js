// ── State ──────────────────────────────────────────────────────────────────
let currentSlippageBps = 50;
let lastQuote = null;
let quoteDebounce = null;

// ── DOM refs ───────────────────────────────────────────────────────────────
const amountIn    = () => document.getElementById("amount-in");
const tokenIn     = () => document.getElementById("token-in");
const tokenOut    = () => document.getElementById("token-out");
const amountOut   = () => document.getElementById("amount-out");
const swapRateEl  = () => document.getElementById("swap-rate");
const quoteResult = () => document.getElementById("quote-result");
const quoteMinOut = () => document.getElementById("quote-min-out");
const quoteImpact = () => document.getElementById("quote-impact");
const swapBtn     = () => document.getElementById("swap-btn");

// ── Slippage chips ─────────────────────────────────────────────────────────
document.addEventListener("click", (e) => {
  const chip = e.target.closest(".slippage-chip");
  if (!chip) return;
  document.querySelectorAll(".slippage-chip").forEach(c => c.classList.remove("active"));
  chip.classList.add("active");
  currentSlippageBps = parseInt(chip.dataset.bps, 10);
  if (amountIn().value.trim()) scheduleQuote();
});

// ── Flip button ────────────────────────────────────────────────────────────
document.getElementById("swap-flip").addEventListener("click", () => {
  const inVal  = tokenIn().value;
  const outVal = tokenOut().value;
  // Swap selectors: find the matching option in the other select
  setSelectValue(tokenIn(),  outVal);
  setSelectValue(tokenOut(), inVal);
  clearQuote();
  if (amountIn().value.trim()) scheduleQuote();
});

function setSelectValue(select, value) {
  for (const opt of select.options) {
    if (opt.value === value) { select.value = value; return; }
  }
  select.selectedIndex = 0;
}

// ── Amount input → auto-quote ──────────────────────────────────────────────
document.getElementById("amount-in").addEventListener("input", () => {
  clearQuote();
  scheduleQuote();
});

document.getElementById("token-in").addEventListener("change",  () => { clearQuote(); scheduleQuote(); });
document.getElementById("token-out").addEventListener("change", () => { clearQuote(); scheduleQuote(); });

function scheduleQuote() {
  clearTimeout(quoteDebounce);
  const val = amountIn().value.trim();
  if (!val || isNaN(parseFloat(val)) || parseFloat(val) <= 0) {
    setSwapBtnState("empty");
    return;
  }
  if (tokenIn().value === tokenOut().value) {
    setSwapBtnState("same-token");
    return;
  }
  setSwapBtnState("loading");
  quoteDebounce = setTimeout(fetchQuote, 400);
}

// ── Quote fetch ────────────────────────────────────────────────────────────
async function fetchQuote() {
  const amount = amountIn().value.trim();
  const tIn    = tokenIn().value;
  const tOut   = tokenOut().value;

  try {
    const resp = await fetch("/trading/quote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token_in: tIn, token_out: tOut, amount, slippage_bps: currentSlippageBps }),
    });
    const payload = await resp.json();
    if (!payload.ok) throw new Error(payload.error?.message || "Quote failed.");
    lastQuote = payload.data;
    displayQuote(lastQuote);
  } catch (err) {
    clearQuote();
    showAlert(err.message || "Could not get a quote.", "error");
    setSwapBtnState("empty");
  }
}

function displayQuote(q) {
  const gross   = parseFloat(q.quoted_amount_out);
  const minOut  = parseFloat(q.min_amount_out);
  const amtIn   = parseFloat(q.amount_in);
  const rate    = gross / amtIn;

  amountOut().textContent = fmt(gross, 6) + " " + q.token_out;
  swapRateEl().textContent = `1 ${q.token_in} ≈ ${fmt(rate, 4)} ${q.token_out}`;

  quoteMinOut().textContent = fmt(minOut, 6) + " " + q.token_out;
  // Demo mode has no real price impact — show a range note
  quoteImpact().textContent = "< 0.01%";

  quoteResult().hidden = false;
  setSwapBtnState("ready");
}

function clearQuote() {
  lastQuote = null;
  amountOut().textContent = "—";
  swapRateEl().textContent = "";
  quoteResult().hidden = true;
}

function fmt(num, decimals) {
  if (isNaN(num)) return "—";
  return num.toLocaleString(undefined, { maximumFractionDigits: decimals });
}

// ── Swap button states ─────────────────────────────────────────────────────
function setSwapBtnState(state) {
  const btn = swapBtn();
  btn.disabled = true;
  if (state === "empty")      btn.textContent = "Enter an amount";
  else if (state === "same-token") btn.textContent = "Select different tokens";
  else if (state === "loading")    btn.textContent = "Getting quote…";
  else if (state === "ready") { btn.textContent = "Swap"; btn.disabled = false; }
}

// ── Swap button → confirm overlay ─────────────────────────────────────────
swapBtn().addEventListener("click", () => {
  if (!lastQuote) return;
  const slippagePct = (currentSlippageBps / 100).toFixed(1) + "%";

  document.getElementById("confirm-pay").textContent      = `${lastQuote.amount_in} ${lastQuote.token_in}`;
  document.getElementById("confirm-receive").textContent  = `${fmt(parseFloat(lastQuote.quoted_amount_out), 6)} ${lastQuote.token_out}`;
  document.getElementById("confirm-min").textContent      = `${fmt(parseFloat(lastQuote.min_amount_out), 6)} ${lastQuote.token_out}`;
  document.getElementById("confirm-slippage").textContent = slippagePct;

  document.getElementById("swap-overlay").hidden = false;
});

document.getElementById("swap-cancel").addEventListener("click", () => {
  document.getElementById("swap-overlay").hidden = true;
});

// ── Confirm → build tx → wallet ───────────────────────────────────────────
document.getElementById("swap-confirm").addEventListener("click", async () => {
  if (!lastQuote) return;

  const overlay     = document.getElementById("swap-overlay");
  const confirmBtn  = document.getElementById("swap-confirm");
  confirmBtn.disabled  = true;
  confirmBtn.textContent = "Sending…";

  try {
    const resp = await fetch("/trading/swap/build-tx", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token_in:     lastQuote.token_in,
        token_out:    lastQuote.token_out,
        amount:       lastQuote.amount_in,
        slippage_bps: currentSlippageBps,
      }),
    });
    const payload = await resp.json();
    if (!payload.ok) throw new Error(payload.error?.message || "Could not build transaction.");

    if (!window.ethereum) throw new Error("No wallet found. Install MetaMask.");
    const txHash = await window.ethereum.request({
      method: "eth_sendTransaction",
      params: [payload.data.tx],
    });

    overlay.hidden = true;
    showAlert("Swap submitted!", "success");
    clearQuote();
    amountIn().value = "";
    setSwapBtnState("empty");
  } catch (err) {
    showAlert(err.message || "Swap failed.");
  } finally {
    confirmBtn.disabled   = false;
    confirmBtn.textContent = "Confirm swap";
  }
});
