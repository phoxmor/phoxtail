# ruff: noqa: E501
"""Create the Phoxtail hatchling homepage and wire the default Wagtail Site.

Seeds the hatchling block definition, replaces Wagtail's welcome page with a
ContentPage containing the hatchling block, and points the default Site at it.

This migration is idempotent: if a non-welcome page already exists at depth 2
it exits cleanly without making changes.
"""

import json
import uuid

from django.db import migrations

_APP_LABEL = "{{ phoxtail_project_name }}"

_COLLECTION_IDENTIFIER = "general_unsorted"
_BLOCK_IDENTIFIER = "hatchling"

_HTML = """\
{% load wagtailcore_tags wagtailimages_tags static phoxtail_design_tags %}

<div id="m3-hatch-{{ block.id }}" class="m3-page">
    <header class="m3-top-bar">
        <div class="m3-top-bar-inner">
            <div class="m3-logo">
                <img src="{% static 'phoxtail_core/phoxtail/logo/name-light.png' %}" alt="Phoxtail" class="m3-logo-img m3-logo-light" />
                <img src="{% static 'phoxtail_core/phoxtail/logo/name-dark.png' %}" alt="Phoxtail" class="m3-logo-img m3-logo-dark" />
            </div>
            <div class="m3-badge-tonal">
                v{% phoxtail_version %}
            </div>
        </div>
    </header>

    <div class="m3-embers" data-m3-embers></div>

    <main class="m3-main-content">
        <div class="m3-hero">
            <div class="m3-phoenix-wrap" data-m3-phoenix>
                <svg class="m3-phoenix" viewBox="0 0 200 220" xmlns="http://www.w3.org/2000/svg">
                    <defs>
                        <radialGradient id="m3-body-g-{{ block.id }}" cx="50%" cy="40%" r="60%">
                            <stop offset="0%" stop-color="rgb(var(--color-accent-50))"/>
                            <stop offset="60%" stop-color="rgb(var(--color-surface-500))"/>
                            <stop offset="100%" stop-color="rgb(var(--color-surface-600))"/>
                        </radialGradient>
                        <radialGradient id="m3-glow-g-{{ block.id }}" cx="50%" cy="50%" r="50%">
                            <stop offset="0%" stop-color="rgb(var(--color-surface-200))" stop-opacity="0.3"/>
                            <stop offset="100%" stop-color="rgb(var(--color-surface-200))" stop-opacity="0"/>
                        </radialGradient>
                        <radialGradient id="m3-cheek-g-{{ block.id }}" cx="50%" cy="50%" r="50%">
                            <stop offset="0%" stop-color="rgb(var(--color-primary-500))" stop-opacity="0.5"/>
                            <stop offset="100%" stop-color="rgb(var(--color-primary-500))" stop-opacity="0"/>
                        </radialGradient>
                        <linearGradient id="m3-shell-g-{{ block.id }}" x1="0%" y1="0%" x2="0%" y2="100%">
                            <stop offset="0%" stop-color="rgb(var(--color-surface-50))"/>
                            <stop offset="100%" stop-color="rgb(var(--color-surface-200))"/>
                        </linearGradient>
                        <filter id="m3-shadow-{{ block.id }}" x="-10%" y="-10%" width="120%" height="120%">
                            <feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="rgb(var(--color-surface-900))" flood-opacity="0.12"/>
                        </filter>
                    </defs>

                    <circle cx="100" cy="120" r="90" fill="url(#m3-glow-g-{{ block.id }})"/>
                    <ellipse cx="100" cy="135" rx="42" ry="46" fill="url(#m3-body-g-{{ block.id }})"/>

                    <path class="m3-wing m3-wing-l" d="M62,135 C35,125 40,150 65,155 Z" fill="rgb(var(--color-surface-600))"/>
                    <path class="m3-wing m3-wing-r" d="M138,135 C165,125 160,150 135,155 Z" fill="rgb(var(--color-surface-600))"/>

                    <circle cx="100" cy="88" r="44" fill="url(#m3-body-g-{{ block.id }})"/>

                    <g class="m3-crest">
                        <path d="M100,46 C95,20 80,10 80,10 C85,25 90,35 96,48 Z" fill="rgb(var(--color-primary-500))"/>
                        <path d="M100,44 C105,15 120,5 120,5 C115,20 108,35 104,46 Z" fill="rgb(var(--color-surface-500))"/>
                        <path d="M100,44 C100,10 105,0 105,0 C95,15 95,30 100,48 Z" fill="rgb(var(--color-secondary-300))"/>
                    </g>

                    <circle cx="70" cy="102" r="11" fill="url(#m3-cheek-g-{{ block.id }})"/>
                    <circle cx="130" cy="102" r="11" fill="url(#m3-cheek-g-{{ block.id }})"/>

                    <g class="m3-eyes-wrap" data-m3-eyes-wrap>
                        <g class="m3-eye" data-m3-eye="left">
                            <circle cx="78" cy="88" r="14" fill="rgb(var(--color-surface-100))"/>
                            <g class="m3-pupil-group" data-m3-pupil>
                                <circle cx="81" cy="88" r="9" fill="rgb(var(--color-surface-900))"/>
                                <circle cx="83" cy="84" r="3.5" fill="rgb(var(--color-surface-50))"/>
                                <circle cx="77" cy="91" r="1.5" fill="rgb(var(--color-surface-50))" opacity="0.8"/>
                            </g>
                        </g>
                        <g class="m3-eye" data-m3-eye="right">
                            <circle cx="122" cy="88" r="14" fill="rgb(var(--color-surface-100))"/>
                            <g class="m3-pupil-group" data-m3-pupil>
                                <circle cx="119" cy="88" r="9" fill="rgb(var(--color-surface-900))"/>
                                <circle cx="117" cy="84" r="3.5" fill="rgb(var(--color-surface-50))"/>
                                <circle cx="123" cy="91" r="1.5" fill="rgb(var(--color-surface-50))" opacity="0.8"/>
                            </g>
                        </g>
                    </g>

                    <path d="M93,98 Q100,108 107,98 Q100,112 93,98 Z" fill="rgb(var(--color-surface-700))"/>
                    <path class="m3-egg" d="M58,135 L68,150 L78,132 L90,155 L100,138 L110,155 L122,132 L132,150 L142,135 A 42 46 0 0 1 58 135 Z" fill="url(#m3-shell-g-{{ block.id }})" filter="url(#m3-shadow-{{ block.id }})"/>
                </svg>
            </div>

            <h1 class="m3-display-title">
                {% if block.value.title %}
                    {{ block.value.title }}
                {% else %}
                    Your phoenix has hatched
                {% endif %}
            </h1>
            <p class="m3-body-subtitle">
                {% if block.value.subtitle %}
                    {{ block.value.subtitle }}
                {% else %}
                    Start building something beautiful
                {% endif %}
            </p>

            <a href="/admin/" class="m3-btn-filled">
                {% icon "dashboard" class="m3-btn-icon" %}
                <span class="m3-btn-label">
                    {% if block.value.cta_text %}
                        {{ block.value.cta_text }}
                    {% else %}
                        Open Dashboard
                    {% endif %}
                </span>
            </a>
        </div>
    </main>

    <footer class="m3-cards-section">
        <div class="m3-cards-container">
            <a href="https://phoxtail.com" target="_blank" rel="noopener" class="m3-card-filled">
                <div class="m3-card-icon-wrap">
                    {% icon "docs" class="m3-card-icon" %}
                </div>
                <div class="m3-card-text">
                    <h2 class="m3-card-title">Documentation</h2>
                    <p class="m3-card-desc">Get acquainted with Phoxtail's core features.</p>
                </div>
            </a>

            <a href="https://github.com/phoxmor/phoxtail" target="_blank" rel="noopener" class="m3-card-filled">
                <div class="m3-card-icon-wrap">
                    {% icon "code" class="m3-card-icon" %}
                </div>
                <div class="m3-card-text">
                    <h2 class="m3-card-title">Source Code</h2>
                    <p class="m3-card-desc">Dig into the code and see how everything works under the hood.</p>
                </div>
            </a>

            <a href="https://github.com/phoxmor/phoxtail/discussions" target="_blank" rel="noopener" class="m3-card-filled">
                <div class="m3-card-icon-wrap">
                    {% icon "groups" class="m3-card-icon" %}
                </div>
                <div class="m3-card-text">
                    <h2 class="m3-card-title">Join the Community</h2>
                    <p class="m3-card-desc">Ask questions, share ideas, and connect with other developers.</p>
                </div>
            </a>
        </div>
    </footer>
</div>"""

_CSS = """\
/* ── Material Design 3 Variables & Scoping ── */
#m3-hatch-{{ block.id }} {
    /* Base Colors */
    --md-sys-color-surface: var(--color-surface-50);
    --md-sys-color-on-surface: var(--color-surface-900);
    --md-sys-color-on-surface-variant: var(--color-surface-600);
    --md-sys-color-outline-variant: var(--color-surface-200);

    /* Tonal Surfaces */
    --md-sys-color-surface-container-lowest: 255, 255, 255;
    --md-sys-color-surface-container-low: var(--color-surface-100);
    --md-sys-color-surface-container: var(--color-surface-200);
    --md-sys-color-surface-container-high: var(--color-surface-300);

    /* Primary Colors */
    --md-sys-color-primary: var(--color-primary-600);
    --md-sys-color-on-primary: 255, 255, 255;
    --md-sys-color-primary-container: var(--color-primary-100);
    --md-sys-color-on-primary-container: var(--color-primary-900);

    position: relative;
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    width: 100%;
    background-color: rgb(var(--md-sys-color-surface));
    color: rgb(var(--md-sys-color-on-surface));
    font-family: var(--font-body, system-ui, sans-serif);
    overflow: hidden;
    transition: background-color 0.3s ease, color 0.3s ease;
}

#m3-hatch-{{ block.id }} *,
#m3-hatch-{{ block.id }} *::before,
#m3-hatch-{{ block.id }} *::after {
    box-sizing: border-box;
}

/* ── Top App Bar (M3 Standard) ── */
#m3-hatch-{{ block.id }} .m3-top-bar {
    width: 100%;
    height: 64px;
    padding: 0 1rem;
    display: flex;
    align-items: center;
    position: absolute;
    top: 0;
    left: 0;
    z-index: 20;
    background: transparent;
}

#m3-hatch-{{ block.id }} .m3-top-bar-inner {
    max-width: 1280px;
    margin: 0 auto;
    width: 100%;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

#m3-hatch-{{ block.id }} .m3-logo-img {
    height: 1.5rem;
    width: auto;
}

#m3-hatch-{{ block.id }} .m3-logo-dark {
    display: none;
}

#m3-hatch-{{ block.id }} .m3-badge-tonal {
    display: inline-flex;
    align-items: center;
    padding: 0.25rem 0.75rem;
    border-radius: 8px; /* M3 small shape */
    font-family: var(--font-ui, system-ui, sans-serif);
    font-weight: var(--font-ui-weight-medium, 500);
    font-size: 0.875rem;
    background-color: rgb(var(--md-sys-color-surface-container-high));
    color: rgb(var(--md-sys-color-on-surface));
    transition: background-color 0.3s ease;
}

/* ── Embers Particle System ── */
#m3-hatch-{{ block.id }} .m3-embers {
    position: absolute;
    inset: 0;
    pointer-events: none;
    z-index: 10;
}

#m3-hatch-{{ block.id }} .m3-ember {
    position: absolute;
    top: 0;
    left: 0;
    border-radius: 50%;
    box-shadow: 0 0 12px currentColor;
}

/* ── Main Content / Hero ── */
#m3-hatch-{{ block.id }} .m3-main-content {
    flex-grow: 1;
    position: relative;
    z-index: 15;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 100px 1.5rem 4rem;
    text-align: center;
}

#m3-hatch-{{ block.id }} .m3-hero {
    max-width: 65ch; /* Prose width for readability */
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;
}

/* ── Phoenix SVG Styles & Animations ── */
#m3-hatch-{{ block.id }} .m3-phoenix-wrap {
    width: 220px;
    height: 240px;
    margin-bottom: 2rem;
    animation: m3-breathe-{{ block.id }} 4s ease-in-out infinite;
}

#m3-hatch-{{ block.id }} .m3-phoenix {
    width: 100%;
    height: 100%;
    overflow: visible;
}

@keyframes m3-breathe-{{ block.id }} {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-12px); }
}

#m3-hatch-{{ block.id }} .m3-crest {
    transform-origin: 100px 46px;
    animation: m3-crest-flicker-{{ block.id }} 2.5s ease-in-out infinite;
}

@keyframes m3-crest-flicker-{{ block.id }} {
    0%, 100% { transform: rotate(0deg) scaleY(1); }
    50% { transform: rotate(2deg) scaleY(1.05); }
}

#m3-hatch-{{ block.id }} .m3-wing-l {
    transform-origin: 65px 145px;
    animation: m3-flutter-l-{{ block.id }} 4s ease-in-out infinite;
}

#m3-hatch-{{ block.id }} .m3-wing-r {
    transform-origin: 135px 145px;
    animation: m3-flutter-r-{{ block.id }} 4s ease-in-out infinite;
}

@keyframes m3-flutter-l-{{ block.id }} {
    0%, 100% { transform: rotate(0deg); }
    50% { transform: rotate(-6deg); }
}

@keyframes m3-flutter-r-{{ block.id }} {
    0%, 100% { transform: rotate(0deg); }
    50% { transform: rotate(6deg); }
}

#m3-hatch-{{ block.id }} .m3-eyes-wrap {
    transform-origin: 100px 88px;
}

#m3-hatch-{{ block.id }} .m3-eye {
    transform-origin: center;
    transition: transform 0.1s cubic-bezier(0.4, 0, 0.2, 1);
}

#m3-hatch-{{ block.id }} .m3-eyes-wrap.is-blinking .m3-eye {
    transform: scaleY(0.1);
}

/* ── Typography ── */
#m3-hatch-{{ block.id }} .m3-display-title {
    font-family: var(--font-heading, inherit);
    font-weight: var(--font-heading-weight-bold, 700);
    font-size: clamp(2rem, 5vw, 3rem);
    line-height: 1.2;
    color: rgb(var(--md-sys-color-on-surface));
    margin: 0 0 1rem;
    letter-spacing: -0.02em;
}

#m3-hatch-{{ block.id }} .m3-body-subtitle {
    font-family: var(--font-body, inherit);
    font-weight: var(--font-body-weight-regular, 400);
    font-size: clamp(1rem, 3vw, 1.25rem);
    line-height: 1.5;
    color: rgb(var(--md-sys-color-on-surface-variant));
    margin: 0 0 2.5rem;
    max-width: 48ch;
}

/* ── Primary Action Button (M3 FAB/Filled Button) ── */
#m3-hatch-{{ block.id }} .m3-btn-filled {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    height: 48px; /* M3 Touch target size */
    padding: 0 1.5rem 0 1rem;
    background-color: rgb(var(--md-sys-color-primary));
    color: rgb(var(--md-sys-color-on-primary));
    border-radius: 9999px; /* Pill shape */
    text-decoration: none;
    font-family: var(--font-ui, inherit);
    font-weight: var(--font-ui-weight-medium, 500);
    font-size: 0.875rem;
    letter-spacing: 0.01em;
    transition: background-color 0.2s ease, box-shadow 0.2s ease;
    /* M3 Elevation Level 1 */
    box-shadow: 0 1px 2px 0 rgba(0,0,0,0.3), 0 1px 3px 1px rgba(0,0,0,0.15);
}

#m3-hatch-{{ block.id }} .m3-btn-filled:hover {
    background-color: rgb(var(--color-primary-700));
    /* M3 Elevation Level 2 */
    box-shadow: 0 1px 2px 0 rgba(0,0,0,0.3), 0 2px 6px 2px rgba(0,0,0,0.15);
}

#m3-hatch-{{ block.id }} .m3-btn-icon {
    width: 1.25rem;
    height: 1.25rem;
    fill: currentColor;
}

/* ── Bottom Cards Section ── */
#m3-hatch-{{ block.id }} .m3-cards-section {
    width: 100%;
    padding: 2rem 1rem 3rem;
    position: relative;
    z-index: 15;
}

#m3-hatch-{{ block.id }} .m3-cards-container {
    max-width: 1024px; /* Narrow container */
    margin: 0 auto;
    display: grid;
    grid-template-columns: 1fr;
    gap: 1rem;
}

@media (min-width: 768px) {
    #m3-hatch-{{ block.id }} .m3-cards-container {
        grid-template-columns: repeat(3, 1fr);
        gap: 1.5rem;
    }
}

/* M3 Filled Card */
#m3-hatch-{{ block.id }} .m3-card-filled {
    display: flex;
    flex-direction: column;
    padding: 1.5rem;
    background-color: rgb(var(--md-sys-color-surface-container-low));
    border-radius: 24px; /* M3 Large Shape */
    text-decoration: none;
    transition: background-color 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
    border: 1px solid transparent;
}

#m3-hatch-{{ block.id }} .m3-card-filled:hover {
    background-color: rgb(var(--md-sys-color-surface-container-low));
    border-color: rgb(var(--md-sys-color-primary));
    transform: translateY(-2px);
}

#m3-hatch-{{ block.id }} .m3-card-icon-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 3rem;
    height: 3rem;
    border-radius: 12px; /* M3 Medium Shape for icons */
    background-color: rgb(var(--md-sys-color-primary-container));
    color: rgb(var(--md-sys-color-on-primary-container));
    margin-bottom: 1.25rem;
}

#m3-hatch-{{ block.id }} .m3-card-icon {
    width: 1.5rem;
    height: 1.5rem;
}

#m3-hatch-{{ block.id }} .m3-card-title {
    font-family: var(--font-heading, inherit);
    font-size: 1.125rem;
    font-weight: var(--font-heading-weight-medium, 500);
    color: rgb(var(--md-sys-color-on-surface));
    margin: 0 0 0.5rem;
    line-height: 1.4;
}

#m3-hatch-{{ block.id }} .m3-card-desc {
    font-family: var(--font-body, inherit);
    font-size: 0.875rem;
    line-height: 1.5;
    color: rgb(var(--md-sys-color-on-surface-variant));
    margin: 0;
}

/* ── Dark Mode (Material 3 Dynamic Mappings) ── */
@media (prefers-color-scheme: dark) {
    #m3-hatch-{{ block.id }} {
        --md-sys-color-surface: var(--color-surface-900);
        --md-sys-color-on-surface: var(--color-surface-100);
        --md-sys-color-on-surface-variant: var(--color-surface-300);
        --md-sys-color-outline-variant: var(--color-surface-700);

        --md-sys-color-surface-container-lowest: var(--color-surface-950);
        --md-sys-color-surface-container-low: var(--color-surface-800);
        --md-sys-color-surface-container: var(--color-surface-700);
        --md-sys-color-surface-container-high: var(--color-surface-600);

        --md-sys-color-primary: var(--color-primary-400);
        --md-sys-color-on-primary: var(--color-surface-900);
        --md-sys-color-primary-container: var(--color-primary-400);
        --md-sys-color-on-primary-container: var(--color-primary-100);
    }

    #m3-hatch-{{ block.id }} .m3-logo-light {
        display: none;
    }

    #m3-hatch-{{ block.id }} .m3-logo-dark {
        display: inline;
    }

    #m3-hatch-{{ block.id }} .m3-btn-filled:hover {
        background-color: rgb(var(--color-primary-300));
    }

    #m3-hatch-{{ block.id }} .m3-card-icon-wrap {
        background-color: rgb(var(--color-primary-400) / 0.15);
    }
}"""

_JS = """\
(function () {
    var root = document.getElementById("m3-hatch-{{ block.id }}");
    if (!root) return;

    /* ── Advanced Eye Tracking (Bounded) ── */
    var phoenixWrap = root.querySelector("[data-m3-phoenix]");
    var pupils = root.querySelectorAll("[data-m3-pupil]");

    if (phoenixWrap && pupils.length) {
        var MAX_OFFSET = 3.5;
        var targetX = 0, targetY = 0;
        var currentX = 0, currentY = 0;
        var EASE = 0.15;
        var tickingEyes = false;

        function onMove(e) {
            var rect = phoenixWrap.getBoundingClientRect();
            var cx = rect.left + rect.width / 2;
            var cy = rect.top + rect.height * 0.40;
            var dx = e.clientX - cx;
            var dy = e.clientY - cy;
            var angle = Math.atan2(dy, dx);
            var dist = Math.min(Math.sqrt(dx * dx + dy * dy) / 40, MAX_OFFSET);

            targetX = Math.cos(angle) * dist;
            targetY = Math.sin(angle) * dist;

            if (!tickingEyes) {
                tickingEyes = true;
                requestAnimationFrame(animateEyes);
            }
        }

        function animateEyes() {
            currentX += (targetX - currentX) * EASE;
            currentY += (targetY - currentY) * EASE;

            for (var i = 0; i < pupils.length; i++) {
                pupils[i].setAttribute("transform", "translate(" + currentX.toFixed(2) + " " + currentY.toFixed(2) + ")");
            }

            if (Math.abs(targetX - currentX) > 0.01 || Math.abs(targetY - currentY) > 0.01) {
                requestAnimationFrame(animateEyes);
            } else {
                tickingEyes = false;
            }
        }

        document.addEventListener("mousemove", onMove);
    }

    /* ── Hardware Accelerated Blinking ── */
    var eyesWrap = root.querySelector("[data-m3-eyes-wrap]");
    if (eyesWrap) {
        function triggerBlink() {
            eyesWrap.classList.add("is-blinking");
            setTimeout(function () {
                eyesWrap.classList.remove("is-blinking");
            }, 150);
            setTimeout(triggerBlink, 2500 + Math.random() * 4000);
        }
        setTimeout(triggerBlink, 2000);
    }

    /* ── Free-Floating Embers (Now with Gravitational Repel) ── */
    var embersEl = root.querySelector("[data-m3-embers]");
    if (embersEl) {
        var EMBER_COUNT = 45;
        var colors = [
            "rgb(var(--color-secondary-400))",
            "rgb(var(--color-primary-500))",
            "rgb(var(--color-accent-500))"
        ];
        var particles = [];

        var emberMouseX = -1000;
        var emberMouseY = -1000;

        root.addEventListener("mousemove", function(e) {
            var rect = root.getBoundingClientRect();
            emberMouseX = e.clientX - rect.left;
            emberMouseY = e.clientY - rect.top;
        });

        root.addEventListener("mouseleave", function() {
            emberMouseX = -1000;
            emberMouseY = -1000;
        });

        function createParticle() {
            var el = document.createElement("span");
            el.className = "m3-ember";
            var size = 2 + Math.random() * 5;
            el.style.width = size + "px";
            el.style.height = size + "px";
            el.style.color = colors[Math.floor(Math.random() * colors.length)];
            el.style.backgroundColor = "currentColor";
            embersEl.appendChild(el);
            return resetParticle({ el: el, size: size }, true);
        }

        function resetParticle(p, isInitial) {
            var rootRect = root.getBoundingClientRect();
            var w = rootRect.width || window.innerWidth;
            var h = rootRect.height || window.innerHeight;
            p.x = Math.random() * w;
            p.y = isInitial ? Math.random() * h : h + 20;

            p.baseVx = (Math.random() - 0.5) * 1.5;
            p.baseVy = -(1 + Math.random() * 1.5);

            p.vx = p.baseVx;
            p.vy = p.baseVy;
            p.life = Math.random() * Math.PI * 2;
            p.el.style.opacity = Math.random() * 0.5 + 0.3;
            return p;
        }

        for (var i = 0; i < EMBER_COUNT; i++) {
            particles.push(createParticle());
        }

        function renderEmbers() {
            var rootRect = root.getBoundingClientRect();
            var w = rootRect.width || window.innerWidth;

            for (var i = 0; i < particles.length; i++) {
                var p = particles[i];

                p.vx += (p.baseVx - p.vx) * 0.05;
                p.vy += (p.baseVy - p.vy) * 0.05;

                var dx = p.x - emberMouseX;
                var dy = p.y - emberMouseY;
                var dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < 120 && dist > 0) {
                    var force = (120 - dist) / 120;
                    p.vx += (dx / dist) * force * 1.5;
                    p.vy += (dy / dist) * force * 1.5;
                }

                p.life += 0.03;
                p.x += p.vx + Math.sin(p.life) * 0.5;
                p.y += p.vy;

                p.el.style.transform = "translate3d(" + p.x.toFixed(2) + "px, " + p.y.toFixed(2) + "px, 0)";

                if (p.y < -50 || p.x < -50 || p.x > w + 50) {
                    resetParticle(p, false);
                }
            }
            requestAnimationFrame(renderEmbers);
        }

        requestAnimationFrame(renderEmbers);
    }
})();"""


def _create_homepage(apps, schema_editor):
    VariantCollection = apps.get_model("phoxtail_streams", "VariantCollection")
    Block = apps.get_model("phoxtail_streams", "Block")
    BlockVariant = apps.get_model("phoxtail_streams", "BlockVariant")
    ContentType = apps.get_model("contenttypes", "ContentType")
    Locale = apps.get_model("wagtailcore", "Locale")
    Page = apps.get_model("wagtailcore", "Page")
    Site = apps.get_model("wagtailcore", "Site")
    ContentPage = apps.get_model(_APP_LABEL, "ContentPage")

    # Idempotency: if a non-welcome page already exists at depth 2, bail out.
    if Page.objects.filter(depth=2).exclude(slug="home").exists():
        return

    collection, _ = VariantCollection.objects.get_or_create(
        identifier=_COLLECTION_IDENTIFIER,
        defaults={
            "name": "General (Unsorted)",
            "description": "The default baseline collection for block variants with no specific grouping.",
        },
    )

    block, _ = Block.objects.get_or_create(
        identifier=_BLOCK_IDENTIFIER,
        defaults={
            "name": "Hatchling",
            "description": "The first page a freshly hatched Phoxtail project displays. A phoenix emerging from its egg — celebrating the birth of a new project.",
            "icon": "home",
        },
    )

    variant, _ = BlockVariant.objects.get_or_create(
        block=block,
        collection=collection,
        identifier="default",
        defaults={
            "name": "Default",
            "description": "Default hatchling variant.",
            "is_default": True,
            "html": _HTML,
            "css": _CSS,
            "javascript": _JS,
        },
    )

    locale = Locale.objects.first()
    if locale is None:
        return

    root = Page.objects.filter(depth=1).first()
    if root is None:
        return

    site = Site.objects.filter(is_default_site=True).first()
    # Temporarily point the site at root so deleting the welcome page
    # doesn't leave the FK dangling.
    if site:
        Site.objects.filter(pk=site.pk).update(root_page_id=root.pk)

    Page.objects.filter(depth=2, slug="home").delete()

    homepage_ct, _ = ContentType.objects.get_or_create(
        app_label=_APP_LABEL,
        model="contentpage",
    )

    homepage = ContentPage.objects.create(
        title="Home",
        slug="home",
        content_type=homepage_ct,
        path="00010001",
        depth=2,
        numchild=0,
        url_path="/home/",
        locale=locale,
    )

    # Write body via raw SQL — SchemaStreamField.get_prep_value() may strip
    # unknown block types before the dynamic registry is fully wired.
    body = json.dumps(
        [
            {
                "type": "hatchling",
                "value": {"variant": variant.pk},
                "id": str(uuid.uuid4()),
            }
        ]
    )
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "UPDATE phoxtail_cms_sitepage SET body = %s WHERE page_ptr_id = %s",
            [body, homepage.pk],
        )

    root.numchild = Page.objects.filter(depth=2).count()
    root.save()

    site_name = _APP_LABEL.replace("_", " ").title()
    if site:
        Site.objects.filter(pk=site.pk).update(
            root_page_id=homepage.pk,
            site_name=site_name,
        )
    else:
        Site.objects.create(
            hostname="localhost",
            root_page=homepage,
            is_default_site=True,
            site_name=site_name,
        )


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("{{ phoxtail_project_name }}", "0001_initial"),
        ("phoxtail_streams", "0001_initial"),
        ("wagtailcore", "0097_embed"),
    ]

    operations = [
        migrations.RunPython(_create_homepage, _noop),
    ]
