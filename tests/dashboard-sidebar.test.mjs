import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const dashboard = await readFile(new URL('../src/pages/DashboardPage.tsx', import.meta.url), 'utf8')
const metricCard = await readFile(new URL('../src/components/MetricCard.tsx', import.meta.url), 'utf8')
const appShell = await readFile(new URL('../src/components/AppShell.tsx', import.meta.url), 'utf8')
const topBar = await readFile(new URL('../src/components/TopBar.tsx', import.meta.url), 'utf8')
const sidebar = await readFile(new URL('../src/components/Sidebar.tsx', import.meta.url), 'utf8')
const styles = await readFile(new URL('../src/styles.css', import.meta.url), 'utf8')
const panel = await readFile(new URL('../src/components/Panel.tsx', import.meta.url), 'utf8')

test('Dashboard uses the Stitch research overview without a duplicate top create action', () => {
  assert.match(dashboard, /className="dashboard-intro"[\s\S]*?<h1>Research Overview<\/h1>/)
  assert.match(dashboard, /Monitor registered cases, uploaded angiogram images, and saved analysis runs\./)
  assert.equal((dashboard.match(/Create new case/g) ?? []).length, 1)
  assert.match(dashboard, /quick-action quick-action--primary[^>]*to="\/cases\?action=create"[^>]*>.*Create new case/s)
})

test('statistic values, labels and colored icons remain, without arrow decorations', () => {
  for (const label of ['Total cases', 'Images uploaded', 'Analyses completed', 'Analyses in progress']) {
    assert.match(dashboard, new RegExp(`label="${label}"`))
  }
  assert.match(dashboard, /summary\?\.cases/)
  assert.match(dashboard, /summary\?\.images/)
  assert.match(metricCard, /className="metric-card__icon"/)
  assert.doesNotMatch(metricCard, /ArrowUpRight|metric-card__arrow/)
})

test('Quick Actions retains Start Analysis navigation without Open workflow text', () => {
  assert.match(dashboard, /className="quick-action" to="\/upload"><span><Activity size=\{17\} \/> Start analysis<\/span><ArrowRight size=\{15\} \/><\/Link>/)
  assert.doesNotMatch(dashboard, /Open workflow|mini-status/)
})

test('Recent Activity tabs filter real case, image and analysis records', () => {
  for (const label of ['All', 'Analyses', 'Uploads']) assert.match(dashboard, new RegExp(`'${label === 'All' ? 'all' : label === 'Analyses' ? 'analysis' : 'upload'}', '${label}'`))
  assert.match(dashboard, /role="group" aria-label="Filter recent activity"/)
  assert.match(dashboard, /aria-pressed=\{activityFilter === filter\}/)
  assert.match(dashboard, /activityFilter === 'analysis' \? item\.kind === 'analysis' : item\.kind === 'image'/)
  assert.match(dashboard, /dashboard-panel-scroll dashboard-panel-scroll--activity/)
})

test('Recent Cases search filters saved case and patient references and View All opens Cases', () => {
  assert.match(dashboard, /aria-label="Search recent cases"[^>]*placeholder="Search cases/)
  assert.match(dashboard, /\$\{record\.case_ref\} \$\{record\.patient_ref\}/)
  assert.match(dashboard, /className="link-button" to="\/cases">View all/)
  assert.match(dashboard, /className="dashboard-panel-scroll dashboard-panel-scroll--records"/)
})

test('Recent Analysis records navigate with their actual saved run identifiers', () => {
  assert.match(dashboard, /to=\{`\/results\?\$\{new URLSearchParams\(\{ run_id: run\.id \}\)/)
  assert.match(dashboard, /run\.status\.replaceAll/)
})

test('recent activity, cases and analyses scroll independently below fixed panel headings', () => {
  assert.match(dashboard, /title="Recent activity"[\s\S]*?dashboard-panel-scroll dashboard-panel-scroll--activity/)
  assert.match(dashboard, /title="Recent cases"[\s\S]*?dashboard-panel-scroll dashboard-panel-scroll--records/)
  assert.match(dashboard, /title="Recent analyses"[\s\S]*?dashboard-panel-scroll dashboard-panel-scroll--records/)
  assert.match(styles, /\.dashboard-panel-scroll \{[^}]*overflow-x: hidden; overflow-y: auto/s)
  assert.match(styles, /\.dashboard-panel-scroll--activity \{[^}]*max-height/)
  assert.match(styles, /\.dashboard-panel-scroll--records \{[^}]*max-height/)
  assert.match(styles, /scrollbar-width: thin/)
})

test('Recent Cases and Recent Analyses show four equal-height rows before scrolling', () => {
  assert.match(dashboard, /title="Recent cases"[\s\S]*?dashboard-panel-scroll dashboard-panel-scroll--records/)
  assert.match(dashboard, /title="Recent analyses"[\s\S]*?dashboard-panel-scroll dashboard-panel-scroll--records/)
  assert.match(styles, /--dashboard-row-height: 43px/)
  assert.match(styles, /min-height: var\(--dashboard-row-height\); padding: 5px 1px/)
  assert.match(styles, /max-height: calc\(4 \* var\(--dashboard-row-height\) \+ 6px\)/)
  assert.match(styles, /\.dashboard-panel-scroll \{[^}]*overflow-y: auto/s)
  assert.match(styles, /\.app-frame--dashboard \.dashboard-record-list,\s*\.app-frame--dashboard \.dashboard-activity-list \{ min-height: 0; \}/)
})

test('all three panel headings and actions stay outside their scrollable record lists', () => {
  const headingIndex = panel.indexOf('<div className="panel__heading">')
  const childrenIndex = panel.indexOf('{children}')
  assert.ok(headingIndex >= 0 && childrenIndex > headingIndex)
  for (const title of ['Recent activity', 'Recent cases', 'Recent analyses']) {
    const titleIndex = dashboard.indexOf(`title="${title}"`)
    const scrollIndex = dashboard.indexOf('dashboard-panel-scroll', titleIndex)
    assert.ok(titleIndex >= 0 && scrollIndex > titleIndex)
  }
})

test('Dashboard desktop rows use the available viewport and short screens do not force page scrolling', () => {
  assert.match(appShell, /location\.pathname === '\/dashboard' \? ' app-frame--dashboard'/)
  assert.match(styles, /\.app-frame--dashboard \{[^}]*height: 100vh;\s*height: 100dvh;[^}]*overflow: hidden/s)
  assert.match(styles, /\.app-frame--dashboard > \.app-body \{[^}]*height: calc\(100dvh - 70px\)[^}]*overflow: hidden/s)
  const desktopGeometry = styles.slice(styles.lastIndexOf('/* Desktop Dashboard geometry'))
  assert.match(desktopGeometry, /\.app-frame--dashboard > \.app-body \{[^}]*flex: 1 1 0;\s*height: auto;\s*min-height: 0;/s)
  assert.match(desktopGeometry, /\.dashboard-page\.dashboard-page--stitch \{[^}]*grid-template-rows: auto minmax\(210px, 1\.12fr\) minmax\(220px, \.88fr\)/s)
  assert.doesNotMatch(styles, /@media \(min-width: 881px\) and \(max-height: 760px\)[\s\S]*?\.dashboard-page \{ min-height: 640px; \}/)
  assert.doesNotMatch(styles, /@media \(min-width: 881px\) and \(max-height: 560px\)[\s\S]*?\.main-content \{ overflow-y: auto; \}/)
  assert.match(styles, /@media \(max-width: 880px\)[\s\S]*?\.main-content \{ height: 100%; min-height: 0; overflow-x: hidden; overflow-y: auto/s)
  assert.match(styles, /@media \(max-width: 640px\)[\s\S]*?height: calc\(100dvh - 62px\)/)
})

test('Analysis Status and Quick Actions do not add internal scrolling', () => {
  assert.match(styles, /\.dashboard-page--stitch \.status-panel,\s*\.dashboard-page--stitch \.quick-panel \{ overflow: visible; \}/)
  const desktopGeometry = styles.slice(styles.lastIndexOf('/* Desktop Dashboard geometry'))
  assert.match(desktopGeometry, /\.app-frame--dashboard \.status-panel,\s*\.app-frame--dashboard \.quick-panel \{ overflow: visible; \}/)
  assert.doesNotMatch(desktopGeometry, /\.app-frame--dashboard \.status-panel,\s*\.app-frame--dashboard \.quick-panel \{ overflow-y: auto; \}/)
  assert.match(desktopGeometry, /\.app-frame--dashboard \.empty-chart-wrap \{[^}]*min-height: 0;[^}]*padding-block: 4px;/s)
  assert.match(desktopGeometry, /\.app-frame--dashboard \.donut-chart \{ flex-basis: 112px; width: 112px; height: 112px; \}/)
})

test('Dashboard activity expands to available space while record panels retain equal heights and four-row previews', () => {
  const desktopGeometry = styles.slice(styles.lastIndexOf('/* Desktop Dashboard geometry'))
  assert.match(desktopGeometry, /\.dashboard-page--stitch \{[^}]*grid-template-rows: auto minmax\(210px, 1\.12fr\) minmax\(220px, \.88fr\)/s)
  assert.match(desktopGeometry, /\.dashboard-grid--top > \.panel,[\s\S]*?\.dashboard-grid--bottom > \.panel \{\s*height: 100%;\s*min-height: 0;/)
  assert.match(desktopGeometry, /\.dashboard-panel-scroll--activity \{\s*flex: 1 1 0;\s*min-height: 0;\s*max-height: none;\s*overflow-y: auto;/)
  assert.match(desktopGeometry, /\.cases-panel \.dashboard-panel-scroll--records,[\s\S]*?max-height: calc\(4 \* var\(--dashboard-row-height\) \+ 6px\);/)
  assert.match(desktopGeometry, /\.dashboard-page--stitch \{\s*--dashboard-row-height: 34px;/)
})

test('Dashboard disclaimer and its dot are removed', () => {
  assert.doesNotMatch(dashboard, /Analysis outputs are predictions and are not clinically validated/)
  assert.doesNotMatch(styles, /dashboard-footer-note|footer-note-dot/)
})

test('sidebar toggle exposes state, persists locally, and closes mobile drawer accessibly', () => {
  assert.match(topBar, /className="topbar-menu-button"[\s\S]*aria-expanded=\{menuExpanded\}[\s\S]*aria-controls="primary-navigation"/)
  assert.match(topBar, /onClick=\{onMenuToggle\}/)
  assert.match(appShell, /artery-analysis:sidebar-collapsed:v2/)
  assert.match(appShell, /preference === null \? true : preference === 'true'/)
  assert.match(appShell, /catch \{\s*return true\s*\}/)
  assert.match(appShell, /localStorage\.setItem\(SIDEBAR_PREFERENCE_KEY, String\(isCollapsed\)\)/)
  assert.match(appShell, /matchMedia\('\(max-width: 880px\)'\)/)
  assert.match(appShell, /aria-label="Close navigation menu"/)
  assert.match(appShell, /event\.key === 'Escape'/)
  assert.match(sidebar, /sidebar--collapsed/)
  assert.match(sidebar, /sidebar--mobile-open/)
})

test('collapsed navigation preserves route links, icon labels and hover/focus tooltips', () => {
  assert.match(sidebar, /title=\{collapsed && !mobileOpen \? label : undefined\}/)
  assert.match(sidebar, /aria-label=\{label\}/)
  assert.match(sidebar, /<NavLink key=\{label\} to=\{to\}/)
  assert.match(sidebar, /<Icon size=\{19\}/)
  assert.match(styles, /\.sidebar--collapsed \.nav-link > span \{ display: none; \}/)
  assert.match(styles, /\.sidebar--collapsed \.nav-link \{ justify-content: center/)
  assert.match(styles, /\.sidebar--collapsed \.nav-link > span \{ display: inline; \}/)
  assert.match(styles, /\.sidebar--mobile-open \.nav-link > span|\.sidebar--collapsed \.nav-link > span \{ display: inline; \}/)
})

test('hamburger precedes the logo; theme and notifications remain wired', () => {
  assert.ok(topBar.indexOf('className="topbar-menu-button"') < topBar.indexOf('className="topbar__brand"'))
  assert.match(topBar, /aria-label="Notifications"/)
  assert.match(topBar, /markAllRead\(\)/)
  assert.match(styles, /html\[data-theme="dark"\] \.topbar/)
  assert.match(styles, /html\[data-theme="dark"\] \.sidebar/)
})
