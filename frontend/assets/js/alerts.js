(function initHourskillAlerts(global) {
  const CONTAINER_ID = "hs-alert-root";
  const STYLE_ID = "hs-alert-style";

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;

    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      #${CONTAINER_ID} {
        position: fixed;
        top: 18px;
        right: 18px;
        display: flex;
        flex-direction: column;
        gap: 10px;
        z-index: 20000;
        max-width: min(420px, calc(100vw - 24px));
      }

      .hs-alert {
        border-radius: 12px;
        border: 1px solid transparent;
        padding: 11px 14px;
        font-size: 0.92rem;
        line-height: 1.4;
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.18);
        animation: hsAlertIn 160ms ease-out;
        background: #ffffff;
        color: #0f172a;
      }

      .hs-alert-success {
        background: #ecfdf3;
        border-color: #86efac;
        color: #166534;
      }

      .hs-alert-error {
        background: #fef2f2;
        border-color: #fca5a5;
        color: #991b1b;
      }

      .hs-alert-hiding {
        animation: hsAlertOut 140ms ease-in forwards;
      }

      @keyframes hsAlertIn {
        from { opacity: 0; transform: translateY(-8px) scale(0.98); }
        to { opacity: 1; transform: translateY(0) scale(1); }
      }

      @keyframes hsAlertOut {
        from { opacity: 1; transform: translateY(0) scale(1); }
        to { opacity: 0; transform: translateY(-6px) scale(0.98); }
      }
    `;

    document.head.appendChild(style);
  }

  function ensureContainer() {
    let root = document.getElementById(CONTAINER_ID);
    if (!root) {
      root = document.createElement("div");
      root.id = CONTAINER_ID;
      document.body.appendChild(root);
    }
    return root;
  }

  function showAlert(message, type) {
    const normalizedType = type === "success" ? "success" : "error";
    const text = String(message || "").trim();
    if (!text) return;

    ensureStyle();
    const root = ensureContainer();

    const item = document.createElement("div");
    item.className = `hs-alert hs-alert-${normalizedType}`;
    item.setAttribute("role", "status");
    item.setAttribute("aria-live", "polite");
    item.textContent = text;

    root.appendChild(item);

    const destroy = () => {
      item.classList.add("hs-alert-hiding");
      setTimeout(() => {
        item.remove();
        if (!root.children.length) {
          root.remove();
        }
      }, 150);
    };

    setTimeout(destroy, 3400);
    item.addEventListener("click", destroy);
  }

  global.showAlert = showAlert;
})(window);
