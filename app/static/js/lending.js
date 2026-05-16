const lendingEndpoints = {
  supply:   "/lending/supply/build-tx",
  withdraw: "/lending/withdraw/build-tx",
  borrow:   "/lending/borrow/build-tx",
  repay:    "/lending/repay/build-tx",
};

const lendingLabels = {
  supply:   "Build supply tx",
  borrow:   "Build borrow tx",
  repay:    "Build repay tx",
  withdraw: "Build withdraw tx",
};

// ── Transaction overlay ────────────────────────────────────────────────────

function showTxOverlay(tx) {
  return new Promise((resolve) => {
    const overlay = document.getElementById("tx-overlay");
    const code = document.getElementById("tx-overlay-code");
    code.textContent = JSON.stringify(tx, null, 2);
    overlay.hidden = false;

    const confirmBtn = document.getElementById("tx-confirm");
    const cancelBtn  = document.getElementById("tx-cancel");

    function cleanup(result) {
      overlay.hidden = true;
      confirmBtn.onclick = null;
      cancelBtn.onclick  = null;
      resolve(result);
    }
    confirmBtn.onclick = () => cleanup(true);
    cancelBtn.onclick  = () => cleanup(false);
  });
}

// ── Chain helpers ──────────────────────────────────────────────────────────

async function sendRawTx(tx) {
  if (!window.ethereum) throw new Error("No injected wallet found.");
  return window.ethereum.request({ method: "eth_sendTransaction", params: [tx] });
}

async function waitForReceipt(txHash) {
  return new Promise((resolve, reject) => {
    function poll() {
      window.ethereum
        .request({ method: "eth_getTransactionReceipt", params: [txHash] })
        .then((receipt) => {
          if (receipt && receipt.blockNumber) {
            if (receipt.status === "0x0" || receipt.status === 0) {
              reject(new Error("Transaction reverted on-chain. Check your token balance and allowance."));
            } else {
              resolve(receipt);
            }
          } else {
            setTimeout(poll, 1500);
          }
        })
        .catch(reject);
    }
    poll();
  });
}

// ── Pending banner ─────────────────────────────────────────────────────────

function showPendingBanner(message) {
  let banner = document.getElementById("pending-tx-banner");
  if (!banner) {
    banner = document.createElement("div");
    banner.id = "pending-tx-banner";
    banner.className = "alert alert-warning";
    banner.style.cssText = "position:fixed;bottom:16px;right:16px;z-index:1000;max-width:360px";
    document.body.appendChild(banner);
  }
  banner.innerHTML = `<span class="spinner" style="display:inline-block;margin-right:8px"></span>${message}`;
  banner.hidden = false;
}

function hidePendingBanner() {
  const banner = document.getElementById("pending-tx-banner");
  if (banner) banner.hidden = true;
}

// ── Track submitted tx on server + poll HTMX ──────────────────────────────

async function trackAndPoll(action, txHash) {
  await fetch("/lending/tx-submitted", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, tx_hash: txHash }),
  });

  showPendingBanner("Confirming transaction…");
  let ticks = 0;
  const interval = setInterval(() => {
    htmx.trigger(document.body, "refresh");
    if (++ticks >= 20) { clearInterval(interval); hidePendingBanner(); }
  }, 3000);

  waitForReceipt(txHash).then(() => {
    clearInterval(interval);
    htmx.trigger(document.body, "refresh");
    hidePendingBanner();
  });
}

// ── Core flow ──────────────────────────────────────────────────────────────

async function fetchBuildTx(action, amount, token) {
  const body = { amount };
  if (token) body.token = token;
  const resp = await fetch(lendingEndpoints[action], {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await resp.json();
  if (!payload.ok) throw new Error(payload.error?.message || "Could not build transaction.");
  return payload.data;
}

async function runLendingAction(action, amount, token) {
  const { tx, needs_approval } = await fetchBuildTx(action, amount, token);

  if (needs_approval) {
    const approveConfirmed = await showTxOverlay(tx);
    if (!approveConfirmed) return;

    const approveTxHash = await sendRawTx(tx);
    showAlert("Approval submitted — waiting for confirmation…", "success");
    showPendingBanner("Approving token spend…");
    await waitForReceipt(approveTxHash);
    hidePendingBanner();
    showAlert("Approved. Building transaction…", "success");

    const { tx: actionTx } = await fetchBuildTx(action, amount, token);
    const actionConfirmed = await showTxOverlay(actionTx);
    if (!actionConfirmed) return;

    const txHash = await sendRawTx(actionTx);
    showAlert("Transaction submitted.", "success");
    await trackAndPoll(action, txHash);
  } else {
    const confirmed = await showTxOverlay(tx);
    if (!confirmed) return;

    const txHash = await sendRawTx(tx);
    showAlert("Transaction submitted.", "success");
    await trackAndPoll(action, txHash);
  }
}

// ── Form handler ───────────────────────────────────────────────────────────

document.addEventListener("submit", async (event) => {
  const form = event.target;
  if (!form.matches("[data-lending-action]")) return;
  event.preventDefault();

  const action    = form.dataset.lendingAction;
  const submitBtn = form.querySelector("button[type=submit]");
  const fd        = new FormData(form);
  const amount    = fd.get("amount");
  const token     = fd.get("token") || null;

  submitBtn.disabled    = true;
  submitBtn.textContent = "Building…";

  try {
    await runLendingAction(action, amount, token);
    form.reset();
  } catch (err) {
    showAlert(err.message || "Lending action failed.");
  } finally {
    submitBtn.disabled    = false;
    submitBtn.textContent = lendingLabels[action];
  }
});
