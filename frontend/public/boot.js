(function () {
  try {
    var boot = JSON.parse(localStorage.getItem("sdd.boot") || "null");
    if (!boot) return;
    var root = document.documentElement;
    for (var name in boot.vars) root.style.setProperty(name, boot.vars[name]);
    root.dataset.scheme = boot.scheme;
    root.dataset.glow = boot.glow ? "on" : "off";
    root.style.colorScheme = boot.scheme;
  } catch (e) {}
})();
