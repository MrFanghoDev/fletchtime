/* Bascule clair/sombre partagée entre index.html, control.html et
 * manual.html. Suit la préférence système par défaut (prefers-color-scheme),
 * sauf si l'utilisateur a explicitement choisi un mode -- mémorisé dans
 * localStorage, comme la langue.
 *
 * Chaque page définit ses propres variables CSS pour les deux modes ; ce
 * fichier ne fait que poser/retirer l'attribut data-theme et piloter les
 * boutons de sélection.
 */

function initTheme() {
  const saved = localStorage.getItem("fletchtime_theme");
  if (saved === "light" || saved === "dark") {
    document.documentElement.setAttribute("data-theme", saved);
  }
  updateThemeButtons();
}

function setTheme(mode) {
  if (mode === "system") {
    document.documentElement.removeAttribute("data-theme");
    localStorage.removeItem("fletchtime_theme");
  } else {
    document.documentElement.setAttribute("data-theme", mode);
    localStorage.setItem("fletchtime_theme", mode);
  }
  updateThemeButtons();
}

function updateThemeButtons() {
  const current = localStorage.getItem("fletchtime_theme") || "system";
  document.querySelectorAll(".theme-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.theme === current);
  });
}

initTheme();
