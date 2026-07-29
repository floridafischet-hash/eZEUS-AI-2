# ruff: noqa: E501

from html import escape

NAVIGATION = (
    ("dashboard", "/", "Übersicht", "dashboard"),
    ("instances", "/admin/instances", "Instanzen", "instances"),
    ("users", "/api/admin-users/page", "Benutzer", "users"),
)

ICONS = {
    "dashboard": (
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 13h6V4H4v9Zm0 7h6v-5H4v5Zm10 0h6v-9h-6v9Zm0-16v5h6V4h-6Z"/></svg>'
    ),
    "instances": (
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v3A2.5 2.5 0 0 1 17.5 11h-11A2.5 2.5 0 0 1 4 8.5v-3Zm0 10A2.5 2.5 0 0 1 6.5 13h11a2.5 2.5 0 0 1 2.5 2.5v3a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 18.5v-3ZM7 6v2h2V6H7Zm0 10v2h2v-2H7Z"/></svg>'
    ),
    "users": (
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 12a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9Zm-8 9a8 8 0 0 1 16 0H4Z"/></svg>'
    ),
    "menu": (
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16v2H4V6Zm0 5h16v2H4v-2Zm0 5h16v2H4v-2Z"/></svg>'
    ),
}


def page_shell(
    *,
    title: str,
    description: str,
    active: str,
    content: str,
    script: str = "",
    eyebrow: str = "eZEUS-AI-2",
    body_class: str = "",
) -> str:
    nav_items: list[str] = []
    for key, href, label, icon in NAVIGATION:
        active_class = " active" if key == active else ""
        aria_current = ' aria-current="page"' if key == active else ""
        nav_items.append(
            f'<a class="nav-item{active_class}" href="{href}"{aria_current}>'
            f'<span class="nav-icon">{ICONS[icon]}</span>'
            f"<span>{escape(label)}</span></a>"
        )
    nav = "".join(nav_items)
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="theme-color" content="#0a0a0a">
  <title>{escape(title)} | eZEUS-AI-2</title>
  <link rel="icon" type="image/png" href="/static/ezeus-logo.png">
  <link rel="stylesheet" href="/static/ezeus-ui.css">
  <script src="/static/ezeus-ui.js" defer></script>
</head>
<body class="{escape(body_class)}">
  <a class="skip-link" href="#main-content">Zum Inhalt springen</a>
  <div class="app-shell">
    <aside class="app-sidebar" id="app-sidebar" aria-label="Hauptnavigation">
      <a class="brand" href="/" aria-label="eZEUS-AI-2 Übersicht">
        <img src="/static/ezeus-logo.png" alt="eZEUS Computersysteme GmbH">
        <span class="product-label">AI-2 Dokumentenautomation</span>
      </a>
      <nav class="sidebar-nav">{nav}</nav>
      <div class="sidebar-footer">
        <span class="status-dot" aria-hidden="true"></span>
        <span>System verbunden</span>
      </div>
    </aside>
    <div class="app-frame">
      <header class="topbar">
        <button class="icon-button mobile-menu" type="button" aria-label="Navigation öffnen"
          aria-controls="app-sidebar" aria-expanded="false">{ICONS["menu"]}</button>
        <div class="topbar-context">
          <span class="topbar-product">eZEUS-AI-2</span>
          <span class="topbar-separator" aria-hidden="true"></span>
          <span class="topbar-page">{escape(title)}</span>
        </div>
        <div class="topbar-account">
          <div class="account-copy">
            <strong>Administration</strong>
            <span>Mandantenverwaltung</span>
          </div>
          <span class="account-avatar" aria-hidden="true">EA</span>
          <img class="topbar-logo" src="/static/ezeus-logo.png" alt="eZEUS Computersysteme GmbH">
        </div>
      </header>
      <main class="main-content" id="main-content" tabindex="-1">
        <div class="page-heading">
          <div>
            <p class="eyebrow">{escape(eyebrow)}</p>
            <h1>{escape(title)}</h1>
            <p class="page-description">{escape(description)}</p>
          </div>
        </div>
        {content}
      </main>
    </div>
  </div>
  <div class="sidebar-backdrop" data-sidebar-close></div>
  {script}
</body>
</html>"""
