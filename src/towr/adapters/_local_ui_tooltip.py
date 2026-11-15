"""Fast hover/focus descriptions shared by inventory and result tags."""

TOOLTIP_STYLE = r'''
.tag-tooltip{position:fixed;z-index:1000;width:max-content;max-width:min(340px,calc(100vw - 24px));max-height:calc(100vh - 24px);overflow:auto;padding:9px 12px;border:1px solid var(--input-border);border-radius:6px;background:var(--surface);color:var(--text);box-shadow:0 4px 16px var(--shadow);font:13px/1.5 system-ui,sans-serif;white-space:pre-wrap;overflow-wrap:anywhere}
.tag-tooltip[hidden]{display:none}
'''

TOOLTIP_SCRIPT = r'''
const tagTooltip=document.createElement('div');tagTooltip.id='tag-tooltip';tagTooltip.className='tag-tooltip';tagTooltip.setAttribute('role','tooltip');tagTooltip.hidden=true;document.body.append(tagTooltip);
let tooltipOwner=null,tooltipTimer=null;
function hideTagTooltip(){
 clearTimeout(tooltipTimer);tooltipTimer=null;if(tooltipOwner)tooltipOwner.removeAttribute('aria-describedby');tooltipOwner=null;tagTooltip.hidden=true;
}
function showTagTooltip(tag){
 hideTagTooltip();if(!tag.isConnected)return;tooltipOwner=tag;tagTooltip.textContent=tag.dataset.tooltip;tagTooltip.hidden=false;tag.setAttribute('aria-describedby',tagTooltip.id);
 const target=tag.getBoundingClientRect(),box=tagTooltip.getBoundingClientRect(),gap=7;
 tagTooltip.style.left=Math.max(12,Math.min(target.left,innerWidth-box.width-12))+'px';
 const top=target.top-box.height-gap>=12?target.top-box.height-gap:target.bottom+gap;
 tagTooltip.style.top=Math.max(12,Math.min(top,innerHeight-box.height-12))+'px';
}
function attachTagTooltip(tag,text){
 tag.removeAttribute('title');tag.dataset.tooltip=text;tag.tabIndex=0;
 tag.addEventListener('pointerenter',()=>{clearTimeout(tooltipTimer);tooltipTimer=setTimeout(()=>showTagTooltip(tag),120);});
 tag.addEventListener('pointerleave',event=>{if(event.relatedTarget&&tagTooltip.contains(event.relatedTarget))return;clearTimeout(tooltipTimer);tooltipTimer=setTimeout(hideTagTooltip,100);});
 tag.addEventListener('focusin',()=>showTagTooltip(tag));
 tag.addEventListener('focusout',event=>{if(!event.relatedTarget||!tag.contains(event.relatedTarget))hideTagTooltip();});
}
tagTooltip.addEventListener('pointerenter',()=>{clearTimeout(tooltipTimer);tooltipTimer=null;});
tagTooltip.addEventListener('pointerleave',event=>{if(!tooltipOwner||!event.relatedTarget||!tooltipOwner.contains(event.relatedTarget))hideTagTooltip();});
document.addEventListener('keydown',event=>{if(event.key==='Escape')hideTagTooltip();});
window.addEventListener('resize',hideTagTooltip);window.addEventListener('scroll',event=>{if(event.target!==tagTooltip)hideTagTooltip();},true);
'''
