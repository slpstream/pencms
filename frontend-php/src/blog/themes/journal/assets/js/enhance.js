// enhance.js — progressive enhancement for Journal theme.

if (navigator.clipboard) {
  for (const code of document.querySelectorAll('pre > code')) {
    const pre = code.parentElement;
    if (pre.querySelector('.copy-code')) continue;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'copy-code';
    button.textContent = 'Copy';
    button.addEventListener('click', async () => {
      await navigator.clipboard.writeText(code.textContent);
      button.textContent = 'Copied';
      setTimeout(() => { button.textContent = 'Copy'; }, 1500);
    });
    pre.append(button);
  }
}
