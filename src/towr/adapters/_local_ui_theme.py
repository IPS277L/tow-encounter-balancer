"""Local UI colour palettes and a persisted, system-aware theme switch."""

THEME_STYLE = r'''
:root{color-scheme:light;
 --page-bg:#f4f5f7;--surface:white;--surface-soft:#fafbfc;--text:#20242c;--muted:#5c6470;--label:#404957;--hint:#667085;--quiet:#8893a3;
 --border:#dfe4eb;--panel-border:#d9dee5;--input-border:#bfc7d2;--code-border:#c9d0da;--divider:#e7ebf0;--button-border:#ccd4df;--tag-border:#cbdcf4;
 --accent:#235ba8;--accent-strong:#1c4c8c;--hover:#edf4ff;--active:#dfeafe;--selected-active:#d0e1fb;
 --solid-bg:#235ba8;--solid-hover:#1c4c8c;--solid-active:#173e73;--on-solid:white;
 --cancel-bg:#a93535;--cancel-hover:#8d2a2a;--cancel-active:#752323;--error:#b02222;
 --success-bg:#e6f2e9;--success-text:#236137;--warning-bg:#fff8e8;--warning-border:#e9d6a7;--warning-text:#78531c;
 --action-text:#586575;--add-hover:#edf5f0;--add-text:#466652;--add-border:#b5cbbd;--add-active:#e1ece5;--add-active-text:#3d5948;--add-active-border:#abc4b5;
 --remove-hover:#fbf0f0;--remove-text:#965959;--remove-border:#d8bcbc;--remove-active:#f0e2e2;--remove-active-text:#814f4f;--remove-active-border:#cfaeae;--shadow:#20242c20;
}
:root[data-theme="dark"]{color-scheme:dark;
 --page-bg:#121821;--surface:#1b2330;--surface-soft:#202b3a;--text:#e5edf7;--muted:#b0bed0;--label:#ced8e6;--hint:#a7b7cd;--quiet:#95a6bc;
 --border:#38495f;--panel-border:#38495f;--input-border:#536780;--code-border:#455b75;--divider:#38495f;--button-border:#536780;--tag-border:#48638a;
 --accent:#a3c7ff;--accent-strong:#c3dcff;--hover:#2a3c56;--active:#334c6c;--selected-active:#3d587b;
 --solid-bg:#295da1;--solid-hover:#3470ba;--solid-active:#285b98;--on-solid:white;
 --cancel-bg:#a43c44;--cancel-hover:#b54b52;--cancel-active:#94353d;--error:#ffb0b6;
 --success-bg:#203c32;--success-text:#b5e1c1;--warning-bg:#3c3221;--warning-border:#796440;--warning-text:#f0d39c;
 --action-text:#c1cedf;--add-hover:#274237;--add-text:#b6dcc3;--add-border:#5b826b;--add-active:#315340;--add-active-text:#d0efda;--add-active-border:#79a78c;
 --remove-hover:#482e36;--remove-text:#efbec5;--remove-border:#94636e;--remove-active:#5b3842;--remove-active-text:#ffd4da;--remove-active-border:#b7808b;--shadow:#00000050;
}
.page-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:18px}.page-heading h1{min-width:0}
#theme-toggle{flex-shrink:0}input,select,progress{accent-color:var(--solid-bg)}input{background:var(--surface);color:var(--text)}
input::placeholder,textarea::placeholder{color:var(--quiet)}
:root[data-theme="dark"] select{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath d='m2 4 4 4 4-4' fill='none' stroke='%23b0bed0' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")}
'''

# Runs before styles are painted and before the main page script.
THEME_INIT = r'''<script>
(()=>{let theme;try{theme=localStorage.getItem('towr-ui-theme');}catch(_){}
document.documentElement.dataset.theme=theme==='light'||theme==='dark'?theme:matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';})();
</script>'''

THEME_SCRIPT = r'''
let themePreference=null;try{themePreference=localStorage.getItem('towr-ui-theme');}catch(_){}
function setTheme(theme,persist=false){
 document.documentElement.dataset.theme=theme;
 const button=byId('theme-toggle'),dark=theme==='dark';button.setAttribute('aria-pressed',String(dark));button.title=dark?'Включить светлую тему':'Включить тёмную тему';
 button.querySelector('path').setAttribute('d',dark?'M12 8a4 4 0 1 0 0 8 4 4 0 1 0 0-8M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5':'M20 14a8 8 0 0 1-10-10A8 8 0 1 0 20 14');
 if(persist){themePreference=theme;try{localStorage.setItem('towr-ui-theme',theme);}catch(_){}}
}
byId('theme-toggle').onclick=()=>setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark',true);
setTheme(document.documentElement.dataset.theme);
matchMedia('(prefers-color-scheme: dark)').addEventListener('change',event=>{if(themePreference!=='light'&&themePreference!=='dark')setTheme(event.matches?'dark':'light');});
'''
