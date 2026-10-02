# ruff: noqa: E501
"""Create the Phoxtail hatchling homepage and wire the default Wagtail Site.

Seeds the hatchling block definition, replaces Wagtail's welcome page with a
ContentPage containing the hatchling block, and points the default Site at it.

This migration is idempotent: if a non-welcome page already exists at depth 2
it exits cleanly without making changes.
"""

import json
import uuid

from django.conf import settings
from django.db import migrations

_APP_LABEL = "{{ phoxtail_project_name }}"

_BLOCK_IDENTIFIER = "hatchling"

_HTML = """\
{% load wagtailcore_tags wagtailimages_tags static phoxtail_design_tags %}

<div id="phoenix-hatchling-{{ block.id }}" class="phoenix-hatchling phx-ground">
    <header class="phoenix-hatchling__top-bar">
        <div class="phoenix-hatchling__top-bar-inner">
            <div class="phoenix-hatchling__logo">
                <img src="{% static 'phoxtail_core/phoxtail/logo/wordmark-on-light.svg' %}" alt="Phoxtail" class="phoenix-hatchling__logo-image phoenix-hatchling__logo-image--light" />
                <img src="{% static 'phoxtail_core/phoxtail/logo/wordmark-on-dark.svg' %}" alt="Phoxtail" class="phoenix-hatchling__logo-image phoenix-hatchling__logo-image--dark" />
            </div>
            <a href="https://releases.phoxtail.com" target="_blank" rel="noopener" class="phx-button phx-button--secondary phx-button--small phoenix-hatchling__version">
                {% icon "deployed_code" class="phoenix-hatchling__accent-icon" %}<span class="phx-sr-only">Version </span>{% phoxtail_version %}<span class="phx-sr-only">, release notes (opens in a new tab)</span>
            </a>
        </div>
    </header>

    <div class="phoenix-hatchling__embers" data-phoenix-hatchling-embers></div>

    <main class="phoenix-hatchling__main">
        <div class="phoenix-hatchling__hero">
            <div class="phoenix-hatchling__phoenix-wrap" data-phoenix-hatchling-phoenix>
                <svg class="phoenix-hatchling__phoenix" viewBox="0 0 200 220" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">
                    <defs>
                        <!-- One light, from the upper left, shapes every rounded part;
                             the body's tones are set in the stylesheet -->
                        <radialGradient id="phoenix-hatchling-body-gradient-{{ block.id }}" cx="38%" cy="30%" r="75%">
                            <stop class="phoenix-hatchling__body-light" offset="0%"/>
                            <stop class="phoenix-hatchling__body-mid" offset="50%"/>
                            <stop class="phoenix-hatchling__body-shade" offset="100%"/>
                        </radialGradient>
                        <linearGradient id="phoenix-hatchling-wing-gradient-{{ block.id }}" x1="0%" y1="0%" x2="0%" y2="100%">
                            <stop class="phoenix-hatchling__body-mid" offset="0%"/>
                            <stop class="phoenix-hatchling__body-shade" offset="100%"/>
                        </linearGradient>
                        <radialGradient id="phoenix-hatchling-shell-gradient-{{ block.id }}" cx="35%" cy="30%" r="85%">
                            <stop offset="0%" stop-color="rgb(var(--color-surface-50))"/>
                            <stop offset="65%" stop-color="rgb(var(--color-surface-100))"/>
                            <stop offset="100%" stop-color="rgb(var(--color-surface-300))"/>
                        </radialGradient>
                        <radialGradient id="phoenix-hatchling-eye-gradient-{{ block.id }}" cx="50%" cy="60%" r="60%">
                            <stop offset="0%" stop-color="rgb(var(--color-surface-50))"/>
                            <stop offset="75%" stop-color="rgb(var(--color-surface-100))"/>
                            <stop offset="100%" stop-color="rgb(var(--color-surface-300))"/>
                        </radialGradient>
                        <!-- The crest is lit like the rest: each feather deepens toward its root -->
                        <linearGradient id="phoenix-hatchling-flame-gradient-{{ block.id }}" x1="0%" y1="100%" x2="0%" y2="0%">
                            <stop offset="0%" stop-color="rgb(var(--color-primary-600))"/>
                            <stop offset="100%" stop-color="rgb(var(--color-primary-300))"/>
                        </linearGradient>
                        <linearGradient id="phoenix-hatchling-flame-core-gradient-{{ block.id }}" x1="0%" y1="100%" x2="0%" y2="0%">
                            <stop offset="0%" stop-color="rgb(var(--color-primary-500))"/>
                            <stop offset="100%" stop-color="rgb(var(--color-secondary-200))"/>
                        </linearGradient>
                        <linearGradient id="phoenix-hatchling-feather-gradient-{{ block.id }}" x1="0%" y1="100%" x2="0%" y2="0%">
                            <stop offset="0%" stop-color="rgb(var(--color-surface-600))"/>
                            <stop offset="100%" stop-color="rgb(var(--color-surface-400))"/>
                        </linearGradient>
                        <!-- The halo's colour is set per theme in the stylesheet -->
                        <radialGradient id="phoenix-hatchling-glow-gradient-{{ block.id }}" cx="50%" cy="50%" r="50%">
                            <stop class="phoenix-hatchling__halo-core" offset="0%"/>
                            <stop class="phoenix-hatchling__halo-mid" offset="50%"/>
                            <stop class="phoenix-hatchling__halo-edge" offset="100%"/>
                        </radialGradient>
                        <radialGradient id="phoenix-hatchling-cheek-gradient-{{ block.id }}" cx="50%" cy="50%" r="50%">
                            <stop offset="0%" stop-color="rgb(var(--color-primary-400))" stop-opacity="0.4"/>
                            <stop offset="100%" stop-color="rgb(var(--color-primary-400))" stop-opacity="0"/>
                        </radialGradient>
                        <filter id="phoenix-hatchling-soft-blur-{{ block.id }}" x="-50%" y="-100%" width="200%" height="300%">
                            <feGaussianBlur stdDeviation="3"/>
                        </filter>
                        <!-- Pupils stay inside the eye, however far they look -->
                        <clipPath id="phoenix-hatchling-eye-left-clip-{{ block.id }}"><circle cx="78" cy="88" r="14"/></clipPath>
                        <clipPath id="phoenix-hatchling-eye-right-clip-{{ block.id }}"><circle cx="122" cy="88" r="14"/></clipPath>
                    </defs>

                    <circle cx="100" cy="120" r="90" fill="url(#phoenix-hatchling-glow-gradient-{{ block.id }})"/>
                    <ellipse class="phoenix-hatchling__shadow" cx="100" cy="190" rx="36" ry="4.5" fill="rgb(var(--color-surface-900))" opacity="0.07" filter="url(#phoenix-hatchling-soft-blur-{{ block.id }})"/>

                    <g class="phoenix-hatchling__bird">
                        <!-- The wings grow from behind the body, so its curve is their joint -->
                        <path class="phoenix-hatchling__wing phoenix-hatchling__wing--left" d="M74,136 C58,132 46,146 52,152 C58,158 68,158 74,156 Z" fill="url(#phoenix-hatchling-wing-gradient-{{ block.id }})"/>
                        <path class="phoenix-hatchling__wing phoenix-hatchling__wing--right" d="M126,136 C142,132 154,146 148,152 C142,158 132,158 126,156 Z" fill="url(#phoenix-hatchling-wing-gradient-{{ block.id }})"/>

                        <ellipse cx="100" cy="135" rx="42" ry="46" fill="url(#phoenix-hatchling-body-gradient-{{ block.id }})"/>

                        <ellipse cx="100" cy="131" rx="30" ry="6" fill="rgb(var(--color-surface-900))" opacity="0.15" filter="url(#phoenix-hatchling-soft-blur-{{ block.id }})"/>
                        <!-- The crest grows from behind the crown, so the head hides every root -->
                        <g class="phoenix-hatchling__crest">
                            <path d="M98,47 C105,16 118,5 118,5 C113,20 104.5,36 101.3,48 Z" fill="url(#phoenix-hatchling-feather-gradient-{{ block.id }})"/>
                            <path d="M100,46 C95,20 80,10 80,10 C85,25 90,35 96,48 Z" fill="url(#phoenix-hatchling-flame-gradient-{{ block.id }})"/>
                            <path d="M100,44 C100,10 105,0 105,0 C95,15 95,30 100,48 Z" fill="url(#phoenix-hatchling-flame-core-gradient-{{ block.id }})"/>
                        </g>

                        <circle cx="100" cy="88" r="44" fill="url(#phoenix-hatchling-body-gradient-{{ block.id }})"/>

                        <circle cx="71" cy="104" r="10" fill="url(#phoenix-hatchling-cheek-gradient-{{ block.id }})"/>
                        <circle cx="129" cy="104" r="10" fill="url(#phoenix-hatchling-cheek-gradient-{{ block.id }})"/>

                        <g class="phoenix-hatchling__eyes" data-phoenix-hatchling-eyes>
                            <g class="phoenix-hatchling__eye phoenix-hatchling__eye--left" data-phoenix-hatchling-eye="left">
                                <g clip-path="url(#phoenix-hatchling-eye-left-clip-{{ block.id }})">
                                    <circle cx="78" cy="88" r="14" fill="url(#phoenix-hatchling-eye-gradient-{{ block.id }})"/>
                                    <g class="phoenix-hatchling__pupil" data-phoenix-hatchling-pupil>
                                        <circle cx="81" cy="88" r="9" fill="rgb(var(--color-surface-900))"/>
                                        <circle cx="83" cy="84" r="3.5" fill="rgb(var(--color-surface-50))"/>
                                        <circle cx="77" cy="91" r="1.5" fill="rgb(var(--color-surface-50))" opacity="0.8"/>
                                    </g>
                                </g>
                            </g>
                            <g class="phoenix-hatchling__eye phoenix-hatchling__eye--right" data-phoenix-hatchling-eye="right">
                                <g clip-path="url(#phoenix-hatchling-eye-right-clip-{{ block.id }})">
                                    <circle cx="122" cy="88" r="14" fill="url(#phoenix-hatchling-eye-gradient-{{ block.id }})"/>
                                    <g class="phoenix-hatchling__pupil" data-phoenix-hatchling-pupil>
                                        <circle cx="119" cy="88" r="9" fill="rgb(var(--color-surface-900))"/>
                                        <circle cx="117" cy="84" r="3.5" fill="rgb(var(--color-surface-50))"/>
                                        <circle cx="123" cy="91" r="1.5" fill="rgb(var(--color-surface-50))" opacity="0.8"/>
                                    </g>
                                </g>
                            </g>
                        </g>

                        <path d="M93,98 Q100,108 107,98 Q100,112 93,98 Z" fill="rgb(var(--color-surface-700))"/>
                        <path class="phoenix-hatchling__egg" d="M58,135 L68,150 L78,132 L90,155 L100,138 L110,155 L122,132 L132,150 L142,135 A 42 46 0 0 1 58 135 Z" fill="url(#phoenix-hatchling-shell-gradient-{{ block.id }})"/>
                    </g>
                </svg>
            </div>

            <h1 class="phoenix-hatchling__title">
                {% if block.value.title %}
                    {{ block.value.title }}
                {% else %}
                    Your phoenix has hatched
                {% endif %}
            </h1>
            <p class="phoenix-hatchling__subtitle">
                {% if block.value.subtitle %}
                    {{ block.value.subtitle }}
                {% else %}
                    Start building something beautiful
                {% endif %}
            </p>

            <a href="/admin/" class="phx-button phx-button--secondary phx-button--large">
                {% icon "dashboard" class="phoenix-hatchling__accent-icon" %}
                <span>
                    {% if block.value.cta_text %}
                        {{ block.value.cta_text }}
                    {% else %}
                        Open dashboard
                    {% endif %}
                </span>
            </a>
        </div>
    </main>

    <footer class="phoenix-hatchling__footer">
        <div class="phoenix-hatchling__cards">
            <a href="https://docs.phoxtail.com/" target="_blank" rel="noopener" class="phx-card phx-card--clickable phoenix-hatchling__card">
                <h2 class="phx-card__title">{% icon "docs" class="phoenix-hatchling__accent-icon" %}Documentation<span class="phx-sr-only"> (opens in a new tab)</span>{% icon "open_in_new" class="phoenix-hatchling__external-icon" %}</h2>
                <p class="phx-card__text">Learn how to build with phoxtail.</p>
            </a>

            <a href="https://source.phoxtail.com" target="_blank" rel="noopener" class="phx-card phx-card--clickable phoenix-hatchling__card">
                <h2 class="phx-card__title">{% icon "code" class="phoenix-hatchling__accent-icon" %}Source code<span class="phx-sr-only"> (opens in a new tab)</span>{% icon "open_in_new" class="phoenix-hatchling__external-icon" %}</h2>
                <p class="phx-card__text">See how phoxtail works under the hood.</p>
            </a>

            <a href="https://community.phoxtail.com" target="_blank" rel="noopener" class="phx-card phx-card--clickable phoenix-hatchling__card">
                <h2 class="phx-card__title">{% icon "groups" class="phoenix-hatchling__accent-icon" %}Community<span class="phx-sr-only"> (opens in a new tab)</span>{% icon "open_in_new" class="phoenix-hatchling__external-icon" %}</h2>
                <p class="phx-card__text">Connect with others who use phoxtail.</p>
            </a>
        </div>
    </footer>
</div>"""

_CSS = """\
/* ── Page ── */
#phoenix-hatchling-{{ block.id }} {
    position: relative;
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    width: 100%;
    font-family: var(--font-body, system-ui, sans-serif);
    overflow: hidden;
}

/* ── Top Bar ── */
#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__top-bar {
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

#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__top-bar-inner {
    max-width: 1024px; /* Lines up with the cards below */
    margin: 0 auto;
    width: 100%;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__logo-image {
    height: 1.5rem;
    width: auto;
}

#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__logo-image--dark {
    display: none;
}

/* Core's secondary button, to the release notes */
#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__version {
    font-variant-numeric: tabular-nums;
}

/* ── Embers Particle System ── */
#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__embers {
    position: absolute;
    inset: 0;
    pointer-events: none;
    z-index: 10;
}

#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__ember {
    position: absolute;
    top: 0;
    left: 0;
    border-radius: 50%;
    box-shadow: 0 0 12px currentColor;
}

/* ── Main Content / Hero ── */
#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__main {
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

#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__hero {
    max-width: 65ch; /* Prose width for readability */
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;
}

/* ── Phoenix SVG Styles & Animations ── */
#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__phoenix-wrap {
    width: 220px;
    height: 240px;
    margin-bottom: 2rem;
}

#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__phoenix {
    width: 100%;
    height: 100%;
    overflow: visible;
}

/* The chick floats; its shadow stays on the ground, shrinking as it rises */
#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__bird {
    animation: phoenix-hatchling-breathe-{{ block.id }} 4s ease-in-out infinite;
}

@keyframes phoenix-hatchling-breathe-{{ block.id }} {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-11px); }
}

#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__shadow {
    transform-origin: 100px 190px;
    animation: phoenix-hatchling-shadow-{{ block.id }} 4s ease-in-out infinite;
}

@keyframes phoenix-hatchling-shadow-{{ block.id }} {
    0%, 100% { transform: scaleX(1); opacity: 0.07; }
    50% { transform: scaleX(0.8); opacity: 0.04; }
}

#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__body-light {
    stop-color: rgb(var(--color-surface-200));
}

#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__body-mid {
    stop-color: rgb(var(--color-surface-400));
}

#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__body-shade {
    stop-color: rgb(var(--color-surface-600));
}

/* A neutral halo, as the rest of the page: colour stays in the small accents */
#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__halo-core {
    stop-color: rgb(var(--color-surface-300));
    stop-opacity: 0.3;
}

#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__halo-mid {
    stop-color: rgb(var(--color-surface-300));
    stop-opacity: 0.12;
}

#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__halo-edge {
    stop-color: rgb(var(--color-surface-300));
    stop-opacity: 0;
}

#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__crest {
    transform-origin: 100px 46px;
    animation: phoenix-hatchling-crest-flicker-{{ block.id }} 2.5s ease-in-out infinite;
}

@keyframes phoenix-hatchling-crest-flicker-{{ block.id }} {
    0%, 100% { transform: rotate(0deg) scaleY(1); }
    50% { transform: rotate(2deg) scaleY(1.05); }
}

#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__wing--left {
    transform-origin: 72px 146px;
    animation: phoenix-hatchling-flutter-left-{{ block.id }} 4s ease-in-out infinite;
}

#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__wing--right {
    transform-origin: 128px 146px;
    animation: phoenix-hatchling-flutter-right-{{ block.id }} 4s ease-in-out infinite;
}

@keyframes phoenix-hatchling-flutter-left-{{ block.id }} {
    0%, 100% { transform: rotate(0deg); }
    50% { transform: rotate(-6deg); }
}

@keyframes phoenix-hatchling-flutter-right-{{ block.id }} {
    0%, 100% { transform: rotate(0deg); }
    50% { transform: rotate(6deg); }
}

/* Each eye closes about its own centre, not the drawing's */
#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__eye {
    transition: transform 0.1s cubic-bezier(0.4, 0, 0.2, 1);
}

#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__eye--left {
    transform-origin: 78px 88px;
}

#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__eye--right {
    transform-origin: 122px 88px;
}

#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__eyes--blinking .phoenix-hatchling__eye {
    transform: scaleY(0.1);
}

@media (prefers-reduced-motion: reduce) {
    #phoenix-hatchling-{{ block.id }} .phoenix-hatchling__bird,
    #phoenix-hatchling-{{ block.id }} .phoenix-hatchling__shadow,
    #phoenix-hatchling-{{ block.id }} .phoenix-hatchling__crest,
    #phoenix-hatchling-{{ block.id }} .phoenix-hatchling__wing {
        animation: none;
    }
}

/* ── Typography ── */
#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__title {
    font-family: var(--font-heading, inherit);
    font-weight: var(--font-heading-weight-bold, 700);
    font-size: clamp(2rem, 5vw, 3rem);
    line-height: 1.2;
    color: rgb(var(--color-surface-900));
    margin: 0 0 1rem;
    letter-spacing: -0.02em;
}

#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__subtitle {
    font-family: var(--font-body, inherit);
    font-weight: var(--font-body-weight-regular, 400);
    font-size: clamp(1rem, 3vw, 1.25rem);
    line-height: 1.5;
    color: rgb(var(--color-surface-600));
    margin: 0 0 2.5rem;
    max-width: 48ch;
}

/* ── Accent Icon ── */
/* The buttons are core's secondary ones and the cards' titles core's own; the
   colour lives in their icons */
#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__accent-icon {
    color: rgb(var(--color-primary-600));
}

/* ── Bottom Cards Section ── */
#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__footer {
    width: 100%;
    padding: 2rem 1rem 3rem;
    position: relative;
    z-index: 15;
}

#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__cards {
    max-width: 1024px; /* Narrow container */
    margin: 0 auto;
    display: grid;
    grid-template-columns: 1fr;
    gap: 1rem;
}

@media (min-width: 768px) {
    #phoenix-hatchling-{{ block.id }} .phoenix-hatchling__cards {
        grid-template-columns: repeat(3, 1fr);
        gap: 1.5rem;
    }
}

/* ── Card ── */
/* Core's card: its surface, shape and hover ring; only the layout is ours */
#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__card {
    display: flex;
    flex-direction: column;
    text-decoration: none;
}

/* Read as a sentence, a step below the title; it ends the card, so the
   card's padding is its only margin */
#phoenix-hatchling-{{ block.id }} .phoenix-hatchling__card .phx-card__text {
    margin-bottom: 0;
    font-size: 0.875rem;
}

/* Opens in a new tab: a quiet arrow at the title's far end */
#phoenix-hatchling-{{ block.id }} .phx-card__title .phoenix-hatchling__external-icon {
    width: 1rem;
    height: 1rem;
    margin-left: auto;
    color: rgb(var(--color-surface-400));
}

/* ── Dark Mode ── */
@media (prefers-color-scheme: dark) {
    #phoenix-hatchling-{{ block.id }} .phoenix-hatchling__title {
        color: rgb(var(--color-surface-100));
    }

    #phoenix-hatchling-{{ block.id }} .phoenix-hatchling__subtitle {
        color: rgb(var(--color-surface-400));
    }

    #phoenix-hatchling-{{ block.id }} .phoenix-hatchling__logo-image--light {
        display: none;
    }

    #phoenix-hatchling-{{ block.id }} .phoenix-hatchling__logo-image--dark {
        display: inline;
    }

    #phoenix-hatchling-{{ block.id }} .phoenix-hatchling__halo-core,
    #phoenix-hatchling-{{ block.id }} .phoenix-hatchling__halo-mid,
    #phoenix-hatchling-{{ block.id }} .phoenix-hatchling__halo-edge {
        stop-color: rgb(var(--color-surface-200));
    }

    #phoenix-hatchling-{{ block.id }} .phoenix-hatchling__halo-core {
        stop-opacity: 0.06;
    }

    #phoenix-hatchling-{{ block.id }} .phoenix-hatchling__halo-mid {
        stop-opacity: 0.025;
    }

    #phoenix-hatchling-{{ block.id }} .phoenix-hatchling__accent-icon {
        color: rgb(var(--color-primary-400));
    }

    #phoenix-hatchling-{{ block.id }} .phx-card__title .phoenix-hatchling__external-icon {
        color: rgb(var(--color-surface-500));
    }
}"""

_JS = """\
(function () {
    var root = document.getElementById("phoenix-hatchling-{{ block.id }}");
    if (!root) return;

    /* ── Advanced Eye Tracking (Bounded) ── */
    var phoenixWrap = root.querySelector("[data-phoenix-hatchling-phoenix]");
    var pupils = root.querySelectorAll("[data-phoenix-hatchling-pupil]");

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
    var eyesWrap = root.querySelector("[data-phoenix-hatchling-eyes]");
    if (eyesWrap) {
        function triggerBlink() {
            eyesWrap.classList.add("phoenix-hatchling__eyes--blinking");
            setTimeout(function () {
                eyesWrap.classList.remove("phoenix-hatchling__eyes--blinking");
            }, 150);
            setTimeout(triggerBlink, 2500 + Math.random() * 4000);
        }
        setTimeout(triggerBlink, 2000);
    }

    /* ── Rising Embers ──
       Every distance is measured in hundredths of the viewport's shorter side
       and every speed per second, so a phone sees the same scene as a desktop,
       only smaller, at any refresh rate. */
    var embersEl = root.querySelector("[data-phoenix-hatchling-embers]");
    if (embersEl && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        var DENSITY = 45 / (1440 * 900); // embers per square pixel of a laptop screen
        var RISE = [2, 5]; // upward speed
        var DRIFT = 1.5; // largest sideways speed
        var SWAY = 1; // speed of the side-to-side sway
        var SWAY_RATE = 1.2; // radians per second
        var REACH = 12; // how close the mouse must come to push an ember
        var PUSH = 90; // strongest push, as an acceleration
        var SETTLE = 2; // how quickly a pushed ember returns to its own course
        var colors = [
            "rgb(var(--color-secondary-400))",
            "rgb(var(--color-primary-500))",
            "rgb(var(--color-accent-500))"
        ];
        var particles = [];

        var unit, width, height;

        function measure() {
            var rect = root.getBoundingClientRect();
            width = rect.width || window.innerWidth;
            height = rect.height || window.innerHeight;
            unit = Math.min(window.innerWidth, window.innerHeight) / 100;
        }

        var mouseX = -1000;
        var mouseY = -1000;

        /* Only a real mouse pushes: a tap on a phone would kick every ember near it */
        root.addEventListener("pointermove", function (e) {
            if (e.pointerType !== "mouse") return;
            var rect = root.getBoundingClientRect();
            mouseX = e.clientX - rect.left;
            mouseY = e.clientY - rect.top;
        });

        root.addEventListener("mouseleave", function () {
            mouseX = -1000;
            mouseY = -1000;
        });

        function between(range) {
            return range[0] + Math.random() * (range[1] - range[0]);
        }

        function createParticle() {
            var el = document.createElement("span");
            el.className = "phoenix-hatchling__ember";
            var size = 2 + Math.random() * 5;
            el.style.width = size + "px";
            el.style.height = size + "px";
            el.style.color = colors[Math.floor(Math.random() * colors.length)];
            el.style.backgroundColor = "currentColor";
            embersEl.appendChild(el);
            return resetParticle({ el: el, size: size }, true);
        }

        function resetParticle(p, isInitial) {
            p.x = Math.random() * width;
            p.y = isInitial ? Math.random() * height : height + 20;

            p.baseVx = (Math.random() - 0.5) * 2 * DRIFT;
            p.baseVy = -between(RISE);

            p.vx = p.baseVx;
            p.vy = p.baseVy;
            p.life = Math.random() * Math.PI * 2;
            p.el.style.opacity = Math.random() * 0.5 + 0.3;
            return p;
        }

        measure();
        var count = Math.max(12, Math.min(45, Math.round(width * height * DENSITY)));
        for (var i = 0; i < count; i++) {
            particles.push(createParticle());
        }

        window.addEventListener("resize", measure);

        var last = performance.now();

        function render(now) {
            /* A long gap (a hidden tab) resumes calmly instead of leaping */
            var dt = Math.min((now - last) / 1000, 0.05);
            last = now;
            var settle = 1 - Math.exp(-SETTLE * dt);
            var reach = REACH * unit;

            for (var i = 0; i < particles.length; i++) {
                var p = particles[i];

                p.vx += (p.baseVx - p.vx) * settle;
                p.vy += (p.baseVy - p.vy) * settle;

                var dx = p.x - mouseX;
                var dy = p.y - mouseY;
                var dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < reach && dist > 0) {
                    /* Eases in from the edge of the reach, so there is no sudden kick */
                    var t = (reach - dist) / reach;
                    var force = t * t * (3 - 2 * t) * PUSH * dt;
                    p.vx += (dx / dist) * force;
                    p.vy += (dy / dist) * force;
                }

                p.life += SWAY_RATE * dt;
                p.x += (p.vx + Math.sin(p.life) * SWAY) * unit * dt;
                p.y += p.vy * unit * dt;

                p.el.style.transform = "translate3d(" + p.x.toFixed(2) + "px, " + p.y.toFixed(2) + "px, 0)";

                if (p.y < -50 || p.x < -50 || p.x > width + 50) {
                    resetParticle(p, false);
                }
            }
            requestAnimationFrame(render);
        }

        requestAnimationFrame(render);
    }
})();"""


def _create_homepage(apps, schema_editor):
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

    block, _ = Block.objects.get_or_create(
        identifier=_BLOCK_IDENTIFIER,
        defaults={
            "name": "Hatchling",
            "description": "The first page a freshly hatched Phoxtail project displays. A phoenix emerging from its egg — celebrating the birth of a new project.",
            "icon": "egg",
            "group": "System",
        },
    )

    variant, _ = BlockVariant.objects.get_or_create(
        block=block,
        collection=None,
        identifier="phoenix",
        defaults={
            "name": "Phoenix",
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

    # WAGTAIL_SITE_NAME carries the "Site name" the user typed during
    # `phoxtail env create` (SITE_NAME in .env). Its settings default is
    # already the title-cased project name, so the `or` only catches an
    # explicitly blank SITE_NAME= — which would otherwise name the site "".
    site_name = getattr(settings, "WAGTAIL_SITE_NAME", None) or _APP_LABEL.replace("_", " ").title()
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
    ]

    operations = [
        migrations.RunPython(_create_homepage, _noop),
    ]
