() => {
  const HTML_NS = 'http://www.w3.org/1999/xhtml';
  const ROLE_ATTR = new Set(['button', 'link', 'tab', 'menuitem', 'checkbox']);
  const EXCL_ANCESTOR = new Set(['script', 'template', 'noscript', 'head']);
  const SKIP_TEXT = new Set(['script', 'style', 'template', 'noscript']);
  const norm = s => (s == null ? '' : String(s)).replace(/\s+/g, ' ').trim();
  const isAriaHidden = n => n.getAttribute('aria-hidden') === 'true';

  // Rule 3, element kinds.
  const isKind = el => {
    const t = el.localName;
    if (t === 'input') return el.type !== 'hidden';
    if (t === 'a' && el.hasAttribute('href')) return true;
    if (t === 'button' || t === 'select' || t === 'textarea') return true;
    return ROLE_ATTR.has(el.getAttribute('role'));
  };

  // Rule 3, DOM-only visibility (no CSS). Returns the exclusion reason or null.
  const exclusion = el => {
    if (el.namespaceURI !== HTML_NS) return 'non_html_namespace';
    if (el.hasAttribute('hidden')) return 'hidden_attr';
    for (let n = el; n; n = n.parentElement) {
      if (n !== el && EXCL_ANCESTOR.has(n.localName)) return 'in_' + n.localName;
      if (n.namespaceURI !== HTML_NS) return 'non_html_ancestor';
      if (isAriaHidden(n)) return 'aria_hidden';
    }
    return null;
  };

  // Rule 3, visible text: descendant text nodes, skipping script/style/template/noscript
  // subtrees and subtrees with the hidden attribute or aria-hidden="true".
  const visibleText = el => {
    let out = '';
    const walk = n => {
      for (let c = n.firstChild; c; c = c.nextSibling) {
        if (c.nodeType === 3) { out += c.data; continue; }
        if (c.nodeType !== 1) continue;
        if (SKIP_TEXT.has(c.localName) || c.hasAttribute('hidden') || isAriaHidden(c)) continue;
        walk(c);
      }
    };
    walk(el);
    return norm(out);
  };

  // Rule 3, accessible name: first non-empty source in this order.
  const accName = el => {
    const txt = visibleText(el);
    if (txt) return [txt, 'text'];
    for (const a of ['aria-label', 'title']) {
      const v = norm(el.getAttribute(a));
      if (v) return [v, a];
    }
    for (const img of el.querySelectorAll('img')) {
      const v = norm(img.getAttribute('alt'));
      if (v) return [v, 'img_alt'];
    }
    for (const a of ['placeholder', 'value']) {
      const v = norm(el.getAttribute(a));
      if (v) return [v, a];
    }
    return ['', 'none'];
  };

  // Rule 4, absolute XPath: /html[1]/body[1]/..., each step = localName + 1-based index
  // among preceding element siblings with the same localName in the HTML namespace.
  const xpathOf = el => {
    const steps = [];
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      let i = 1;
      for (let s = n.previousElementSibling; s; s = s.previousElementSibling) {
        if (s.localName === n.localName && s.namespaceURI === HTML_NS) i++;
      }
      steps.unshift(n.localName + '[' + i + ']');
    }
    return '/' + steps.join('/');
  };

  const all = document.querySelectorAll('*');
  const excluded = {};
  const candidates = [];
  for (const el of all) {
    if (!isKind(el)) continue;
    const why = exclusion(el);
    if (why) { excluded[why] = (excluded[why] || 0) + 1; continue; }
    const [name, nameSource] = accName(el);
    const xpath = xpathOf(el);
    const back = document.evaluate(xpath, document, null,
      XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
    const attrs = {};
    for (const a of el.attributes) attrs[a.name] = a.value;
    candidates.push({
      xpath, xpathRoundTrip: back === el,
      tag: el.localName,
      type: el.localName === 'input' ? el.type : null,
      roleAttr: el.getAttribute('role'),
      multiple: el.localName === 'select' ? el.multiple : null,
      size: el.localName === 'select' ? el.size : null,
      name, nameSource, nameLength: [...name].length,
      attrs,
    });
  }
  return { elementCount: all.length, excluded, candidates };
}
