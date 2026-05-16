async function connectWallet(email = null) {
  if (!window.ethereum) {
    showWalletStatus("No injected wallet was found. Please install MetaMask.", "error");
    return;
  }

  const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
  const chainIdHex = await window.ethereum.request({ method: "eth_chainId" });
  const address = accounts[0];
  const chainId = Number.parseInt(chainIdHex, 16);

  const nonceResponse = await fetch("/auth/nonce", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ address, chain_id: chainId }),
  });
  const noncePayload = await nonceResponse.json();
  if (!noncePayload.ok) {
    throw new Error(noncePayload.error?.message || "Could not start wallet sign-in.");
  }

  const signature = await window.ethereum.request({
    method: "personal_sign",
    params: [noncePayload.data.message, address],
  });

  const verifyBody = { address, message: noncePayload.data.message, signature };
  if (email) verifyBody.email = email;

  const verifyResponse = await fetch("/auth/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(verifyBody),
  });
  const verifyPayload = await verifyResponse.json();
  if (!verifyPayload.ok) {
    throw new Error(verifyPayload.error?.message || "Wallet sign-in failed.");
  }

  showWalletStatus(`Connected ${address}`, "success");
  window.location.href = "/";
}

async function logoutWallet() {
  await fetch("/auth/logout", { method: "POST", headers: { "Content-Type": "application/json" } });
  window.location.href = "/auth/connect";
}

function showWalletStatus(message, type) {
  const alertRegion = document.querySelector("#alerts");
  if (alertRegion) {
    const el = document.createElement("div");
    el.className = `alert alert-${type}`;
    el.textContent = message;
    alertRegion.appendChild(el);
    setTimeout(() => el.remove(), 6000);
  }
  document.dispatchEvent(new CustomEvent("walletStatus", { detail: { message, type } }));
}

// MetaMask account or chain change
if (window.ethereum) {
  window.ethereum.on("accountsChanged", (accounts) => {
    if (accounts.length === 0) {
      logoutWallet();
    } else {
      fetch("/auth/logout", { method: "POST", headers: { "Content-Type": "application/json" } }).then(() => {
        window.location.href = "/auth/connect";
      });
    }
  });

  window.ethereum.on("chainChanged", () => {
    window.location.reload();
  });
}

document.addEventListener("click", (event) => {
  if (event.target.closest("[data-wallet-connect]")) {
    const btn = event.target.closest("[data-wallet-connect]");
    const mode = btn.dataset.mode || "login";
    const email = mode === "signup"
      ? (document.getElementById("signup-email")?.value.trim() || null)
      : null;

    btn.disabled = true;
    connectWallet(email)
      .catch((error) => {
        showWalletStatus(error.message || "Wallet connection failed.", "error");
      })
      .finally(() => { btn.disabled = false; });
  }

  if (event.target.matches("#wallet-logout")) {
    logoutWallet().catch(() => { window.location.href = "/auth/connect"; });
  }
});
