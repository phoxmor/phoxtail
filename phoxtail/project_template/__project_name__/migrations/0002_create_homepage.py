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

<div id="phxt-hatch-{{ block.id }}" class="phxt-page">
    <header class="phxt-top-bar">
        <div class="phxt-top-bar-inner">
            <div class="phxt-logo">
                <img src="{% static 'phoxtail_core/phoxtail/logo/wordmark-on-light.svg' %}" alt="Phoxtail" class="phxt-logo-img phxt-logo-light" />
                <img src="{% static 'phoxtail_core/phoxtail/logo/wordmark-on-dark.svg' %}" alt="Phoxtail" class="phxt-logo-img phxt-logo-dark" />
            </div>
            <div class="phxt-badge-tonal">
                v{% phoxtail_version %}
            </div>
        </div>
    </header>

    <div class="phxt-embers" data-phxt-embers></div>

    <main class="phxt-main-content">
        <div class="phxt-hero">
            <div class="phxt-phoenix-wrap" data-phxt-phoenix>
                <svg class="phxt-phoenix" viewBox="0 0 200 220" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">
                    <defs>
                        <!-- One light, from the upper left, shapes every rounded part;
                             the body's tones are set in the stylesheet -->
                        <radialGradient id="phxt-body-g-{{ block.id }}" cx="38%" cy="30%" r="75%">
                            <stop class="phxt-body-light" offset="0%"/>
                            <stop class="phxt-body-mid" offset="50%"/>
                            <stop class="phxt-body-shade" offset="100%"/>
                        </radialGradient>
                        <linearGradient id="phxt-wing-g-{{ block.id }}" x1="0%" y1="0%" x2="0%" y2="100%">
                            <stop class="phxt-body-mid" offset="0%"/>
                            <stop class="phxt-body-shade" offset="100%"/>
                        </linearGradient>
                        <radialGradient id="phxt-shell-g-{{ block.id }}" cx="35%" cy="30%" r="85%">
                            <stop offset="0%" stop-color="rgb(var(--color-surface-50))"/>
                            <stop offset="65%" stop-color="rgb(var(--color-surface-100))"/>
                            <stop offset="100%" stop-color="rgb(var(--color-surface-300))"/>
                        </radialGradient>
                        <radialGradient id="phxt-eye-g-{{ block.id }}" cx="50%" cy="60%" r="60%">
                            <stop offset="0%" stop-color="rgb(var(--color-surface-50))"/>
                            <stop offset="75%" stop-color="rgb(var(--color-surface-100))"/>
                            <stop offset="100%" stop-color="rgb(var(--color-surface-300))"/>
                        </radialGradient>
                        <!-- The crest is lit like the rest: each feather deepens toward its root -->
                        <linearGradient id="phxt-flame-g-{{ block.id }}" x1="0%" y1="100%" x2="0%" y2="0%">
                            <stop offset="0%" stop-color="rgb(var(--color-primary-600))"/>
                            <stop offset="100%" stop-color="rgb(var(--color-primary-300))"/>
                        </linearGradient>
                        <linearGradient id="phxt-flame-core-g-{{ block.id }}" x1="0%" y1="100%" x2="0%" y2="0%">
                            <stop offset="0%" stop-color="rgb(var(--color-primary-500))"/>
                            <stop offset="100%" stop-color="rgb(var(--color-secondary-200))"/>
                        </linearGradient>
                        <linearGradient id="phxt-feather-g-{{ block.id }}" x1="0%" y1="100%" x2="0%" y2="0%">
                            <stop offset="0%" stop-color="rgb(var(--color-surface-600))"/>
                            <stop offset="100%" stop-color="rgb(var(--color-surface-400))"/>
                        </linearGradient>
                        <!-- The halo's colour is set per theme in the stylesheet -->
                        <radialGradient id="phxt-glow-g-{{ block.id }}" cx="50%" cy="50%" r="50%">
                            <stop class="phxt-halo-core" offset="0%"/>
                            <stop class="phxt-halo-mid" offset="50%"/>
                            <stop class="phxt-halo-edge" offset="100%"/>
                        </radialGradient>
                        <radialGradient id="phxt-cheek-g-{{ block.id }}" cx="50%" cy="50%" r="50%">
                            <stop offset="0%" stop-color="rgb(var(--color-primary-400))" stop-opacity="0.4"/>
                            <stop offset="100%" stop-color="rgb(var(--color-primary-400))" stop-opacity="0"/>
                        </radialGradient>
                        <filter id="phxt-soft-{{ block.id }}" x="-50%" y="-100%" width="200%" height="300%">
                            <feGaussianBlur stdDeviation="3"/>
                        </filter>
                        <!-- Pupils stay inside the eye, however far they look -->
                        <clipPath id="phxt-eye-l-{{ block.id }}"><circle cx="78" cy="88" r="14"/></clipPath>
                        <clipPath id="phxt-eye-r-{{ block.id }}"><circle cx="122" cy="88" r="14"/></clipPath>
                    </defs>

                    <circle cx="100" cy="120" r="90" fill="url(#phxt-glow-g-{{ block.id }})"/>
                    <ellipse class="phxt-ground" cx="100" cy="190" rx="36" ry="4.5" fill="rgb(var(--color-surface-900))" opacity="0.07" filter="url(#phxt-soft-{{ block.id }})"/>

                    <g class="phxt-bird">
                        <!-- The wings grow from behind the body, so its curve is their joint -->
                        <path class="phxt-wing phxt-wing-l" d="M74,136 C58,132 46,146 52,152 C58,158 68,158 74,156 Z" fill="url(#phxt-wing-g-{{ block.id }})"/>
                        <path class="phxt-wing phxt-wing-r" d="M126,136 C142,132 154,146 148,152 C142,158 132,158 126,156 Z" fill="url(#phxt-wing-g-{{ block.id }})"/>

                        <ellipse cx="100" cy="135" rx="42" ry="46" fill="url(#phxt-body-g-{{ block.id }})"/>

                        <ellipse cx="100" cy="131" rx="30" ry="6" fill="rgb(var(--color-surface-900))" opacity="0.15" filter="url(#phxt-soft-{{ block.id }})"/>
                        <!-- The crest grows from behind the crown, so the head hides every root -->
                        <g class="phxt-crest">
                            <path d="M98,47 C105,16 118,5 118,5 C113,20 104.5,36 101.3,48 Z" fill="url(#phxt-feather-g-{{ block.id }})"/>
                            <path d="M100,46 C95,20 80,10 80,10 C85,25 90,35 96,48 Z" fill="url(#phxt-flame-g-{{ block.id }})"/>
                            <path d="M100,44 C100,10 105,0 105,0 C95,15 95,30 100,48 Z" fill="url(#phxt-flame-core-g-{{ block.id }})"/>
                        </g>

                        <circle cx="100" cy="88" r="44" fill="url(#phxt-body-g-{{ block.id }})"/>

                        <circle cx="71" cy="104" r="10" fill="url(#phxt-cheek-g-{{ block.id }})"/>
                        <circle cx="129" cy="104" r="10" fill="url(#phxt-cheek-g-{{ block.id }})"/>

                        <g class="phxt-eyes-wrap" data-phxt-eyes-wrap>
                            <g class="phxt-eye phxt-eye-l" data-phxt-eye="left">
                                <g clip-path="url(#phxt-eye-l-{{ block.id }})">
                                    <circle cx="78" cy="88" r="14" fill="url(#phxt-eye-g-{{ block.id }})"/>
                                    <g class="phxt-pupil-group" data-phxt-pupil>
                                        <circle cx="81" cy="88" r="9" fill="rgb(var(--color-surface-900))"/>
                                        <circle cx="83" cy="84" r="3.5" fill="rgb(var(--color-surface-50))"/>
                                        <circle cx="77" cy="91" r="1.5" fill="rgb(var(--color-surface-50))" opacity="0.8"/>
                                    </g>
                                </g>
                            </g>
                            <g class="phxt-eye phxt-eye-r" data-phxt-eye="right">
                                <g clip-path="url(#phxt-eye-r-{{ block.id }})">
                                    <circle cx="122" cy="88" r="14" fill="url(#phxt-eye-g-{{ block.id }})"/>
                                    <g class="phxt-pupil-group" data-phxt-pupil>
                                        <circle cx="119" cy="88" r="9" fill="rgb(var(--color-surface-900))"/>
                                        <circle cx="117" cy="84" r="3.5" fill="rgb(var(--color-surface-50))"/>
                                        <circle cx="123" cy="91" r="1.5" fill="rgb(var(--color-surface-50))" opacity="0.8"/>
                                    </g>
                                </g>
                            </g>
                        </g>

                        <path d="M93,98 Q100,108 107,98 Q100,112 93,98 Z" fill="rgb(var(--color-surface-700))"/>
                        <path class="phxt-egg" d="M58,135 L68,150 L78,132 L90,155 L100,138 L110,155 L122,132 L132,150 L142,135 A 42 46 0 0 1 58 135 Z" fill="url(#phxt-shell-g-{{ block.id }})"/>
                    </g>
                </svg>
            </div>

            <h1 class="phxt-display-title">
                {% if block.value.title %}
                    {{ block.value.title }}
                {% else %}
                    Your phoenix has hatched
                {% endif %}
            </h1>
            <p class="phxt-body-subtitle">
                {% if block.value.subtitle %}
                    {{ block.value.subtitle }}
                {% else %}
                    Start building something beautiful
                {% endif %}
            </p>

            <a href="/admin/" class="phxt-btn-filled">
                {% icon "dashboard" class="phxt-btn-icon" %}
                <span class="phxt-btn-label">
                    {% if block.value.cta_text %}
                        {{ block.value.cta_text }}
                    {% else %}
                        Open dashboard
                    {% endif %}
                </span>
            </a>
        </div>
    </main>

    <footer class="phxt-cards-section">
        <div class="phxt-cards-container">
            <a href="https://docs.phoxtail.com/" target="_blank" rel="noopener" class="phxt-card-filled">
                <div class="phxt-card-icon-wrap">
                    {% icon "docs" class="phxt-card-icon" %}
                </div>
                <div class="phxt-card-text">
                    <h2 class="phxt-card-title">Documentation</h2>
                    <p class="phxt-card-desc">Everything you need to start building with phoxtail.</p>
                </div>
            </a>

            <a href="https://github.com/phoxmor/phoxtail" target="_blank" rel="noopener" class="phxt-card-filled">
                <div class="phxt-card-icon-wrap">
                    {% icon "code" class="phxt-card-icon" %}
                </div>
                <div class="phxt-card-text">
                    <h2 class="phxt-card-title">Source code</h2>
                    <p class="phxt-card-desc">Explore how phoxtail works under the hood.</p>
                </div>
            </a>

            <a href="https://community.phoxtail.com" target="_blank" rel="noopener" class="phxt-card-filled">
                <div class="phxt-card-icon-wrap">
                    {% icon "groups" class="phxt-card-icon" %}
                </div>
                <div class="phxt-card-text">
                    <h2 class="phxt-card-title">Join the community</h2>
                    <p class="phxt-card-desc">Ask questions, share ideas, and connect with the phoxtail community.</p>
                </div>
            </a>
        </div>
    </footer>
</div>"""

_CSS = """\
/* ── Variables & Scoping ── */
#phxt-hatch-{{ block.id }} {
    /* Base Colors */
    --sys-color-surface: var(--color-surface-50);
    --sys-color-on-surface: var(--color-surface-900);
    --sys-color-on-surface-variant: var(--color-surface-600);

    position: relative;
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    width: 100%;
    background-color: rgb(var(--sys-color-surface));
    color: rgb(var(--sys-color-on-surface));
    font-family: var(--font-body, system-ui, sans-serif);
    overflow: hidden;
    transition: background-color 0.3s ease, color 0.3s ease;
}

#phxt-hatch-{{ block.id }} *,
#phxt-hatch-{{ block.id }} *::before,
#phxt-hatch-{{ block.id }} *::after {
    box-sizing: border-box;
}

/* ── Top Bar ── */
#phxt-hatch-{{ block.id }} .phxt-top-bar {
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

#phxt-hatch-{{ block.id }} .phxt-top-bar-inner {
    max-width: 1024px; /* Lines up with the cards below */
    margin: 0 auto;
    width: 100%;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

#phxt-hatch-{{ block.id }} .phxt-logo-img {
    height: 1.5rem;
    width: auto;
}

#phxt-hatch-{{ block.id }} .phxt-logo-dark {
    display: none;
}

#phxt-hatch-{{ block.id }} .phxt-badge-tonal {
    display: inline-flex;
    align-items: center;
    padding: 0.25rem 0.75rem;
    border-radius: 8px;
    font-family: var(--font-ui, system-ui, sans-serif);
    font-weight: var(--font-ui-weight-medium, 500);
    font-size: 0.875rem;
    /* The cards' glass and shadow, so the badge reads as one of them */
    background-color: rgb(var(--color-surface-50) / 0.6);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    box-shadow:
        0 0 24px -6px rgb(var(--color-surface-900) / 0.08),
        0 20px 40px -16px rgb(var(--color-surface-900) / 0.12);
    color: rgb(var(--sys-color-on-surface));
}

/* ── Embers Particle System ── */
#phxt-hatch-{{ block.id }} .phxt-embers {
    position: absolute;
    inset: 0;
    pointer-events: none;
    z-index: 10;
}

#phxt-hatch-{{ block.id }} .phxt-ember {
    position: absolute;
    top: 0;
    left: 0;
    border-radius: 50%;
    box-shadow: 0 0 12px currentColor;
}

/* ── Main Content / Hero ── */
#phxt-hatch-{{ block.id }} .phxt-main-content {
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

#phxt-hatch-{{ block.id }} .phxt-hero {
    max-width: 65ch; /* Prose width for readability */
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;
}

/* ── Phoenix SVG Styles & Animations ── */
#phxt-hatch-{{ block.id }} .phxt-phoenix-wrap {
    width: 220px;
    height: 240px;
    margin-bottom: 2rem;
}

#phxt-hatch-{{ block.id }} .phxt-phoenix {
    width: 100%;
    height: 100%;
    overflow: visible;
}

/* The chick floats; its shadow stays on the ground, shrinking as it rises */
#phxt-hatch-{{ block.id }} .phxt-bird {
    animation: phxt-breathe-{{ block.id }} 4s ease-in-out infinite;
}

@keyframes phxt-breathe-{{ block.id }} {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-11px); }
}

#phxt-hatch-{{ block.id }} .phxt-ground {
    transform-origin: 100px 190px;
    animation: phxt-ground-{{ block.id }} 4s ease-in-out infinite;
}

@keyframes phxt-ground-{{ block.id }} {
    0%, 100% { transform: scaleX(1); opacity: 0.07; }
    50% { transform: scaleX(0.8); opacity: 0.04; }
}

#phxt-hatch-{{ block.id }} .phxt-body-light {
    stop-color: rgb(var(--color-surface-200));
}

#phxt-hatch-{{ block.id }} .phxt-body-mid {
    stop-color: rgb(var(--color-surface-400));
}

#phxt-hatch-{{ block.id }} .phxt-body-shade {
    stop-color: rgb(var(--color-surface-600));
}

/* A neutral halo, as the rest of the page: colour stays in the small accents */
#phxt-hatch-{{ block.id }} .phxt-halo-core {
    stop-color: rgb(var(--color-surface-300));
    stop-opacity: 0.3;
}

#phxt-hatch-{{ block.id }} .phxt-halo-mid {
    stop-color: rgb(var(--color-surface-300));
    stop-opacity: 0.12;
}

#phxt-hatch-{{ block.id }} .phxt-halo-edge {
    stop-color: rgb(var(--color-surface-300));
    stop-opacity: 0;
}

#phxt-hatch-{{ block.id }} .phxt-crest {
    transform-origin: 100px 46px;
    animation: phxt-crest-flicker-{{ block.id }} 2.5s ease-in-out infinite;
}

@keyframes phxt-crest-flicker-{{ block.id }} {
    0%, 100% { transform: rotate(0deg) scaleY(1); }
    50% { transform: rotate(2deg) scaleY(1.05); }
}

#phxt-hatch-{{ block.id }} .phxt-wing-l {
    transform-origin: 72px 146px;
    animation: phxt-flutter-l-{{ block.id }} 4s ease-in-out infinite;
}

#phxt-hatch-{{ block.id }} .phxt-wing-r {
    transform-origin: 128px 146px;
    animation: phxt-flutter-r-{{ block.id }} 4s ease-in-out infinite;
}

@keyframes phxt-flutter-l-{{ block.id }} {
    0%, 100% { transform: rotate(0deg); }
    50% { transform: rotate(-6deg); }
}

@keyframes phxt-flutter-r-{{ block.id }} {
    0%, 100% { transform: rotate(0deg); }
    50% { transform: rotate(6deg); }
}

/* Each eye closes about its own centre, not the drawing's */
#phxt-hatch-{{ block.id }} .phxt-eye {
    transition: transform 0.1s cubic-bezier(0.4, 0, 0.2, 1);
}

#phxt-hatch-{{ block.id }} .phxt-eye-l {
    transform-origin: 78px 88px;
}

#phxt-hatch-{{ block.id }} .phxt-eye-r {
    transform-origin: 122px 88px;
}

#phxt-hatch-{{ block.id }} .phxt-eyes-wrap.is-blinking .phxt-eye {
    transform: scaleY(0.1);
}

@media (prefers-reduced-motion: reduce) {
    #phxt-hatch-{{ block.id }} .phxt-bird,
    #phxt-hatch-{{ block.id }} .phxt-ground,
    #phxt-hatch-{{ block.id }} .phxt-crest,
    #phxt-hatch-{{ block.id }} .phxt-wing {
        animation: none;
    }
}

/* ── Typography ── */
#phxt-hatch-{{ block.id }} .phxt-display-title {
    font-family: var(--font-heading, inherit);
    font-weight: var(--font-heading-weight-bold, 700);
    font-size: clamp(2rem, 5vw, 3rem);
    line-height: 1.2;
    color: rgb(var(--sys-color-on-surface));
    margin: 0 0 1rem;
    letter-spacing: -0.02em;
}

#phxt-hatch-{{ block.id }} .phxt-body-subtitle {
    font-family: var(--font-body, inherit);
    font-weight: var(--font-body-weight-regular, 400);
    font-size: clamp(1rem, 3vw, 1.25rem);
    line-height: 1.5;
    color: rgb(var(--sys-color-on-surface-variant));
    margin: 0 0 2.5rem;
    max-width: 48ch;
}

/* ── Primary Action Button ── */
#phxt-hatch-{{ block.id }} .phxt-btn-filled {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    height: 48px;
    padding: 0 1.5rem 0 1rem;
    /* The cards' glass; as on their tiles, the colour lives in the icon */
    background-color: rgb(var(--color-surface-50) / 0.6);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    color: rgb(var(--sys-color-on-surface));
    border-radius: 9999px; /* Pill shape */
    text-decoration: none;
    font-family: var(--font-ui, inherit);
    font-weight: var(--font-ui-weight-medium, 500);
    font-size: 0.875rem;
    letter-spacing: 0.01em;
    position: relative;
    isolation: isolate;
    box-shadow:
        0 0 24px -6px rgb(var(--color-surface-900) / 0.08),
        0 20px 40px -16px rgb(var(--color-surface-900) / 0.12);
}

#phxt-hatch-{{ block.id }} .phxt-btn-icon {
    width: 1.25rem;
    height: 1.25rem;
    fill: currentColor;
    color: rgb(var(--color-primary-600));
}

/* ── Bottom Cards Section ── */
#phxt-hatch-{{ block.id }} .phxt-cards-section {
    width: 100%;
    padding: 2rem 1rem 3rem;
    position: relative;
    z-index: 15;
}

#phxt-hatch-{{ block.id }} .phxt-cards-container {
    max-width: 1024px; /* Narrow container */
    margin: 0 auto;
    display: grid;
    grid-template-columns: 1fr;
    gap: 1rem;
}

@media (min-width: 768px) {
    #phxt-hatch-{{ block.id }} .phxt-cards-container {
        grid-template-columns: repeat(3, 1fr);
        gap: 1.5rem;
    }
}

/* ── Card ── */
/* Borderless glass: the embers stay visible through it, and the shadow is
   tinted by the surface so it lifts the card rather than smudging the page.
   The faint halo reaches every side, so the top edge still reads where the
   card and page share a colour. */
#phxt-hatch-{{ block.id }} .phxt-card-filled {
    display: flex;
    flex-direction: column;
    padding: 1.5rem;
    background-color: rgb(var(--color-surface-50) / 0.6);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-radius: 1.5rem;
    box-shadow:
        0 0 24px -6px rgb(var(--color-surface-900) / 0.08),
        0 20px 40px -16px rgb(var(--color-surface-900) / 0.12);
    text-decoration: none;
    position: relative;
    isolation: isolate;
}

/* The hover state lives on its own layer and only fades in, so the blurred
   glass itself never changes.
   The page is surface-50 too, so the card brightens past it and its shadow
   deepens, as if lifted toward you. Shared by the cards and the button. */
#phxt-hatch-{{ block.id }} .phxt-card-filled::before,
#phxt-hatch-{{ block.id }} .phxt-btn-filled::before {
    content: "";
    position: absolute;
    inset: 0;
    z-index: -1;
    border-radius: inherit;
    background-color: rgb(255 255 255 / 0.85);
    /* Adds to the resting shadow, which stays: a touch deeper, never darker */
    box-shadow:
        0 0 24px -6px rgb(var(--color-surface-900) / 0.02),
        0 22px 42px -16px rgb(var(--color-surface-900) / 0.04);
    opacity: 0;
    pointer-events: none;
    /* Just long enough to soften the switch; an even curve, since the change
       is only a few shades and an ease-out would leave the last step alone */
    transition: opacity 0.1s ease-in-out;
}

#phxt-hatch-{{ block.id }} .phxt-card-filled:hover::before,
#phxt-hatch-{{ block.id }} .phxt-btn-filled:hover::before {
    opacity: 1;
}

#phxt-hatch-{{ block.id }} .phxt-card-icon-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 3rem;
    height: 3rem;
    border-radius: 12px;
    /* A quiet surface tile, as on the dashboard widgets: the colour lives in
       the icon alone */
    background: rgb(var(--color-surface-100) / 0.7);
    color: rgb(var(--color-primary-600));
    margin-bottom: 1.25rem;
}

#phxt-hatch-{{ block.id }} .phxt-card-icon {
    width: 1.5rem;
    height: 1.5rem;
}

#phxt-hatch-{{ block.id }} .phxt-card-title {
    font-family: var(--font-heading, inherit);
    font-size: 1.125rem;
    font-weight: var(--font-heading-weight-medium, 500);
    color: rgb(var(--sys-color-on-surface));
    margin: 0 0 0.5rem;
    line-height: 1.4;
}

#phxt-hatch-{{ block.id }} .phxt-card-desc {
    font-family: var(--font-body, inherit);
    font-size: 0.875rem;
    line-height: 1.5;
    color: rgb(var(--sys-color-on-surface-variant));
    margin: 0;
}

/* ── Dark Mode ── */
@media (prefers-color-scheme: dark) {
    #phxt-hatch-{{ block.id }} {
        --sys-color-surface: var(--color-surface-950);
        --sys-color-on-surface: var(--color-surface-100);
        --sys-color-on-surface-variant: var(--color-surface-300);
    }

    #phxt-hatch-{{ block.id }} .phxt-logo-light {
        display: none;
    }

    #phxt-hatch-{{ block.id }} .phxt-logo-dark {
        display: inline;
    }

    #phxt-hatch-{{ block.id }} .phxt-halo-core,
    #phxt-hatch-{{ block.id }} .phxt-halo-mid,
    #phxt-hatch-{{ block.id }} .phxt-halo-edge {
        stop-color: rgb(var(--color-surface-200));
    }

    #phxt-hatch-{{ block.id }} .phxt-halo-core {
        stop-opacity: 0.06;
    }

    #phxt-hatch-{{ block.id }} .phxt-halo-mid {
        stop-opacity: 0.025;
    }

    #phxt-hatch-{{ block.id }} .phxt-btn-filled {
        background-color: rgb(var(--color-surface-50) / 0.05);
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
    }

    #phxt-hatch-{{ block.id }} .phxt-btn-icon {
        color: rgb(var(--color-primary-400));
    }

    #phxt-hatch-{{ block.id }} .phxt-card-filled {
        background-color: rgb(var(--color-surface-50) / 0.05);
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
    }

    #phxt-hatch-{{ block.id }} .phxt-card-filled::before,
    #phxt-hatch-{{ block.id }} .phxt-btn-filled::before {
        background-color: rgb(var(--color-surface-50) / 0.04);
        box-shadow: none;
    }

    #phxt-hatch-{{ block.id }} .phxt-badge-tonal {
        background-color: rgb(var(--color-surface-50) / 0.05);
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
    }

    #phxt-hatch-{{ block.id }} .phxt-card-icon-wrap {
        background: rgb(var(--color-surface-50) / 0.06);
        color: rgb(var(--color-primary-400));
    }
}"""

_JS = """\
(function () {
    var root = document.getElementById("phxt-hatch-{{ block.id }}");
    if (!root) return;

    /* ── Advanced Eye Tracking (Bounded) ── */
    var phoenixWrap = root.querySelector("[data-phxt-phoenix]");
    var pupils = root.querySelectorAll("[data-phxt-pupil]");

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
    var eyesWrap = root.querySelector("[data-phxt-eyes-wrap]");
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

    /* ── Rising Embers ──
       Every distance is measured in hundredths of the viewport's shorter side
       and every speed per second, so a phone sees the same scene as a desktop,
       only smaller, at any refresh rate. */
    var embersEl = root.querySelector("[data-phxt-embers]");
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
            el.className = "phxt-ember";
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
