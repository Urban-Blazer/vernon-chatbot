(function () {
  var script = document.currentScript;
  var host = script.getAttribute("data-host") || script.src.replace(/\/embed\.js(\?.*)?$/, "");
  var position = script.getAttribute("data-position") || "bottom-right";
  var buttonColor = script.getAttribute("data-button-color") || "#2563eb";
  var lang = script.getAttribute("data-lang") || "en";
  var width = script.getAttribute("data-width") || "400";
  var height = script.getAttribute("data-height") || "600";

  var isOpen = false;

  // Create button
  var btn = document.createElement("button");
  btn.setAttribute("aria-label", "Open chat");
  btn.style.cssText =
    "position:fixed;z-index:99999;border:none;cursor:pointer;border-radius:50%;" +
    "width:56px;height:56px;display:flex;align-items:center;justify-content:center;" +
    "box-shadow:0 4px 12px rgba(0,0,0,0.15);background:" + buttonColor + ";";

  if (position === "bottom-left") {
    btn.style.bottom = "20px";
    btn.style.left = "20px";
  } else {
    btn.style.bottom = "20px";
    btn.style.right = "20px";
  }

  btn.innerHTML =
    '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';

  // Create iframe container
  var container = document.createElement("div");
  container.style.cssText =
    "position:fixed;z-index:99998;display:none;border:none;border-radius:12px;" +
    "overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,0.15);" +
    "width:" + Math.min(parseInt(width), window.innerWidth - 40) + "px;" +
    "height:" + Math.min(parseInt(height), window.innerHeight - 100) + "px;";

  if (position === "bottom-left") {
    container.style.bottom = "88px";
    container.style.left = "20px";
  } else {
    container.style.bottom = "88px";
    container.style.right = "20px";
  }

  var iframe = document.createElement("iframe");
  iframe.src = host + "/embed?lang=" + lang;
  iframe.style.cssText = "width:100%;height:100%;border:none;";
  iframe.setAttribute("title", "Vernon Chatbot");
  iframe.setAttribute("loading", "lazy");
  container.appendChild(iframe);

  btn.addEventListener("click", function () {
    isOpen = !isOpen;
    container.style.display = isOpen ? "block" : "none";
    btn.innerHTML = isOpen
      ? '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
      : '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
    btn.setAttribute("aria-label", isOpen ? "Close chat" : "Open chat");
  });

  document.body.appendChild(container);
  document.body.appendChild(btn);
})();
