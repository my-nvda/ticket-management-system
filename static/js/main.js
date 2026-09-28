/**
 * TICKET MANAGEMENT SYSTEM - ACCESSIBLE VANILLA JAVASCRIPT
 * Handles a11y live announcements, EN/AR language toggle, form validation, and AJAX status updates.
 */

document.addEventListener('DOMContentLoaded', () => {
    initLiveAnnouncer();
    initLanguageToggle();
    initFormValidation();
    initCopyReference();
    initStatusUpdateForm();
});

/**
 * Screen Reader Live Announcer Utility
 */
function initLiveAnnouncer() {
    let announcer = document.getElementById('live-announcer');
    if (!announcer) {
        announcer = document.createElement('div');
        announcer.id = 'live-announcer';
        announcer.className = 'sr-only';
        announcer.setAttribute('aria-live', 'polite');
        announcer.setAttribute('aria-atomic', 'true');
        document.body.appendChild(announcer);
    }
}

function announce(message) {
    let announcer = document.getElementById('live-announcer');
    if (!announcer) {
        initLiveAnnouncer();
        announcer = document.getElementById('live-announcer');
    }
    if (!announcer) return;
    
    // Clear and re-populate to trigger screen reader polite update
    announcer.textContent = '';
    setTimeout(() => {
        announcer.textContent = message;
    }, 100);
}

/**
 * Internationalization (EN / AR) & RTL Switcher
 */
function initLanguageToggle() {
    const langBtn = document.getElementById('lang-toggle-btn');
    if (!langBtn) return;

    // Load saved preference or default to 'en'
    const savedLang = localStorage.getItem('app_lang') || 'en';
    applyLanguage(savedLang);

    langBtn.addEventListener('click', () => {
        const currentLang = document.documentElement.getAttribute('lang') || 'en';
        const newLang = currentLang === 'en' ? 'ar' : 'en';
        applyLanguage(newLang);
        localStorage.setItem('app_lang', newLang);
        
        const announceMsg = newLang === 'ar' ? 'تم تغيير اللغة إلى العربية' : 'Language changed to English';
        announce(announceMsg);
    });
}

function applyLanguage(lang) {
    const isArabic = lang === 'ar';
    const htmlEl = document.documentElement;
    const langBtn = document.getElementById('lang-toggle-btn');

    htmlEl.setAttribute('lang', lang);
    htmlEl.setAttribute('dir', isArabic ? 'rtl' : 'ltr');

    // 1. Update text content & placeholders
    const translatableElements = document.querySelectorAll('[data-en][data-ar]');
    translatableElements.forEach(el => {
        const text = isArabic ? el.getAttribute('data-ar') : el.getAttribute('data-en');
        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
            el.placeholder = text;
        } else {
            const childElements = Array.from(el.children);
            if (childElements.length === 0) {
                el.textContent = text;
            } else {
                let textUpdated = false;
                el.childNodes.forEach(child => {
                    if (child.nodeType === Node.TEXT_NODE && child.textContent.trim().length > 0) {
                        child.textContent = ' ' + text.trim() + ' ';
                        textUpdated = true;
                    }
                });
                if (!textUpdated) {
                    const hasTranslatableChildren = childElements.some(child => child.hasAttribute('data-en'));
                    if (!hasTranslatableChildren) {
                        el.textContent = text;
                    }
                }
            }
        }
    });

    // 2. Dynamic Screen Reader ARIA Labels Translation
    const ariaElements = document.querySelectorAll('[data-en-aria][data-ar-aria]');
    ariaElements.forEach(el => {
        const ariaText = isArabic ? el.getAttribute('data-ar-aria') : el.getAttribute('data-en-aria');
        el.setAttribute('aria-label', ariaText);
    });

    // 3. Dynamic Image Alt Descriptions Translation
    const altElements = document.querySelectorAll('[data-en-alt][data-ar-alt]');
    altElements.forEach(el => {
        const altText = isArabic ? el.getAttribute('data-ar-alt') : el.getAttribute('data-en-alt');
        el.setAttribute('alt', altText);
    });

    // 4. Update language toggle button state
    if (langBtn) {
        langBtn.setAttribute('aria-label', isArabic ? 'Switch Language to English' : 'تغيير اللغة إلى العربية');
        langBtn.textContent = isArabic ? '🌐 English' : '🌐 العربية';
    }
}

/**
 * Accessible Form Validation
 */
function initFormValidation() {
    const form = document.getElementById('ticket-form');
    if (!form) return;

    form.addEventListener('submit', (event) => {
        let isValid = true;
        let firstInvalidField = null;

        const inputs = form.querySelectorAll('input[required], textarea[required]');
        
        inputs.forEach(input => {
            const errorSpan = document.getElementById(`${input.id}-error`);
            if (!input.value.trim()) {
                isValid = false;
                input.setAttribute('aria-invalid', 'true');
                
                const lang = document.documentElement.getAttribute('lang');
                const errorMsg = lang === 'ar' ? 'هذا الحقل مطلوب' : 'This field is required';
                
                if (errorSpan) {
                    errorSpan.textContent = errorMsg;
                    errorSpan.classList.remove('sr-only');
                }
                
                if (!firstInvalidField) {
                    firstInvalidField = input;
                }
            } else {
                input.removeAttribute('aria-invalid');
                if (errorSpan) {
                    errorSpan.textContent = '';
                    errorSpan.classList.add('sr-only');
                }
            }
        });

        if (!isValid) {
            event.preventDefault();
            if (firstInvalidField) {
                firstInvalidField.focus();
                const lang = document.documentElement.getAttribute('lang');
                const fieldLabel = firstInvalidField.previousElementSibling ? firstInvalidField.previousElementSibling.textContent.replace('*', '').trim() : 'Field';
                const announceMsg = lang === 'ar' 
                    ? `خطأ في نموذج الإدخال. يرجى المراجعة والتحقق من حقل ${fieldLabel}.`
                    : `Form validation error. Please check the ${fieldLabel} field.`;
                announce(announceMsg);
            }
        }
    });
}

/**
 * Copy Reference Number Helper
 */
function initCopyReference() {
    const copyBtn = document.getElementById('copy-ref-btn');
    if (!copyBtn) return;

    copyBtn.addEventListener('click', () => {
        const refText = copyBtn.getAttribute('data-ref');
        if (!refText) return;

        navigator.clipboard.writeText(refText).then(() => {
            const lang = document.documentElement.getAttribute('lang');
            const msg = lang === 'ar' ? 'تم نسخ الرقم المرجعي للحافظة!' : 'Reference number copied to clipboard!';
            
            const originalText = copyBtn.textContent;
            copyBtn.textContent = lang === 'ar' ? '✅ تم النسخ' : '✅ Copied!';
            announce(msg);

            setTimeout(() => {
                copyBtn.textContent = originalText;
            }, 2500);
        }).catch(err => {
            console.error('Copy failed', err);
        });
    });
}

/**
 * AJAX Ticket Status Update Handler with Polite ARIA Announcements
 */
function initStatusUpdateForm() {
    const statusForm = document.getElementById('status-update-form');
    if (!statusForm) return;

    statusForm.addEventListener('submit', (e) => {
        e.preventDefault();
        
        const ticketId = statusForm.getAttribute('data-ticket-id');
        const selectEl = document.getElementById('status-select');
        const submitBtn = document.getElementById('update-status-btn');
        const newStatus = selectEl.value;

        submitBtn.disabled = true;
        
        const formData = new FormData();
        formData.append('status', newStatus);

        fetch(`/admin/ticket/${ticketId}/status`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            submitBtn.disabled = false;
            if (data.success) {
                // Update badge visually on ticket detail page
                const detailBadge = document.getElementById('detail-status-badge');
                if (detailBadge) {
                    detailBadge.className = `status-badge status-${data.status} status-badge-lg`;
                    detailBadge.textContent = data.status_label;
                }

                // Screen Reader Polite Notification (WCAG 2.1 Requirement)
                const lang = document.documentElement.getAttribute('lang');
                const updateMsg = lang === 'ar' 
                    ? `تم تحديث حالة التذكرة بنجاح إلى: ${data.status_label}` 
                    : `Ticket status successfully updated to ${data.status_label}`;
                
                announce(updateMsg);

                // Show visual toast feedback
                showStatusFeedback(data.message, 'success');
            } else {
                announce(`Error updating status: ${data.message}`);
                showStatusFeedback(data.message, 'error');
            }
        })
        .catch(err => {
            submitBtn.disabled = false;
            console.error('Status update failed', err);
            announce('Failed to update status. Please try again.');
            showStatusFeedback('Failed to update status.', 'error');
        });
    });
}

function showStatusFeedback(message, type) {
    const feedbackBox = document.getElementById('status-feedback');
    if (!feedbackBox) return;

    feedbackBox.textContent = message;
    feedbackBox.className = `status-feedback alert alert-${type}`;
    feedbackBox.style.marginTop = '1rem';

    setTimeout(() => {
        feedbackBox.textContent = '';
        feedbackBox.className = 'status-feedback sr-only';
    }, 4000);
}
