document.addEventListener('DOMContentLoaded', () => {
    let navlinks = Array.from(document.querySelectorAll('nav>a'));
    let inlinelinks = document.querySelectorAll('section a[href^="#"]');
    for (let link of [...navlinks, ...inlinelinks]) {
        link.addEventListener('click', showSection);
    }

    showSection({
        target: navlinks.find(a => a.hash === location.hash) || navlinks[0],
    });

    let inputs = document.querySelectorAll('input');
    for (let input of inputs) {
        let button = document.createElement('button');
        button.textContent = "Copy";
        button.addEventListener('click', copyText.bind(undefined, input));
        input.insertAdjacentElement('beforebegin', button);
    }
});

function showSection(event) {
    let target = event.target;
    let id = target.hash.substring(1);
    for (let section of document.querySelectorAll('section')) {
        section.style.display = section.id === id ? '' : 'none';
    }
    for (let link of document.querySelectorAll('nav>a')) {
        link.classList[link === target ? 'add' : 'remove']('selected');
    }

    if (event.preventDefault) {
        // This isn't the dummy object from the initial page load.
        // Get the first thing after the heading.  If it's on screen, the whole
        // heading is too, and that should be enough for the user to see that
        // the section changed.  Otherwise, we'll scroll the page to show the
        // section.
        event.preventDefault();
        let section = document.getElementById(id);
        let item = section.firstElementChild.nextElementSibling;
        let rect = item.getBoundingClientRect();
        let viewport_height = document.documentElement.clientHeight;
        if (rect.top >= viewport_height) {
            section.scrollIntoView({behavior: 'smooth', block: 'start'});
        }
    }
}

function copyText(input, event) {
    let button = document.activeElement;
    input.select();
    input.focus({preventScroll: true});
    let copied = document.execCommand('copy');
    if (copied) {
        input.setSelectionRange(0, 0);
        button.focus();
        input.classList.remove('flash');
        requestAnimationFrame(() => input.classList.add('flash'));

        let span = document.createElement('span');
        span.textContent = "Copied!";
        span.className = 'copied';
        span.style.top = (button.offsetTop) + 'px';
        span.style.left = (button.offsetLeft + button.offsetWidth) + 'px';
        span.style.lineHeight = (button.offsetHeight) + 'px';
        button.insertAdjacentElement('afterend', span);
        setTimeout(() => span.remove(), 1500);
    } else {
        alert("Sorry, this copy button doesn't work.  You'll have to copy and paste the old-fashioned way.");
    }
}
