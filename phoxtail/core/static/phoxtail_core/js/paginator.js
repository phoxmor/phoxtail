/**
 * A paginator's page, asked for from below the list, brings the list's top
 * back into view: what the paginator sits in, scrolled to its start in
 * whatever scrolls it (the window, or Wagtail's <main>). It starts with the
 * request, as the redraw may replace the paginator before the answer is in.
 * Smooth, unless the reader asks for less motion.
 */

document.addEventListener('htmx:beforeRequest', function (event) {
    var paginator = event.target.closest && event.target.closest('.phx-paginator');
    if (!paginator) {
        return;
    }
    var list = paginator.parentElement;
    if (list.getBoundingClientRect().top >= 0) {
        return;
    }
    var still = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    list.scrollIntoView({ block: 'start', behavior: still ? 'auto' : 'smooth' });
});
