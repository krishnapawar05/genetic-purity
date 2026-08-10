/**
 * Authentication Client Validation & Interactivity
 */
document.addEventListener('DOMContentLoaded', () => {
    // Signup Form Validation
    const signupForm = document.getElementById('signup-form');
    if (signupForm) {
        const passwordInput = document.getElementById('password');
        const confirmInput = document.getElementById('confirmPassword');
        const emailInput = document.getElementById('email');
        const mobileInput = document.getElementById('mobileNumber');
        
        const strengthBar = document.getElementById('strength-bar');
        const strengthText = document.getElementById('strength-text');
        const matchError = document.getElementById('match-error');

        // Password Strength Meter
        const strengthContainer = document.getElementById('strength-meter-container');
        if (passwordInput && strengthBar && strengthContainer) {
            passwordInput.addEventListener('input', () => {
                const val = passwordInput.value;
                if (!val) {
                    strengthContainer.classList.add('hidden');
                    return;
                }
                strengthContainer.classList.remove('hidden');
                
                let score = 0;
                
                if (val.length >= 8) score++;
                if (/[A-Z]/.test(val)) score++;
                if (/[a-z]/.test(val)) score++;
                if (/[0-9]/.test(val)) score++;
                if (/[^A-Za-z0-9]/.test(val)) score++;

                let width = '0%';
                let color = '#ef4444';
                let label = 'Very Weak';

                switch (score) {
                    case 1: width = '20%'; color = '#ef4444'; label = 'Weak'; break;
                    case 2: width = '40%'; color = '#f59e0b'; label = 'Fair'; break;
                    case 3: width = '60%'; color = '#eab308'; label = 'Good'; break;
                    case 4: width = '80%'; color = '#10b981'; label = 'Strong'; break;
                    case 5: width = '100%'; color = '#059669'; label = 'Excellent'; break;
                    default: width = '0%'; color = '#ef4444'; label = 'Too Short'; break;
                }

                strengthBar.style.width = width;
                strengthBar.style.backgroundColor = color;
                if (strengthText) {
                    strengthText.textContent = label;
                    strengthText.style.color = color;
                }
            });
        }

        // Password Match Verification
        if (confirmInput && passwordInput && matchError) {
            const verifyMatch = () => {
                if (confirmInput.value.length > 0 && confirmInput.value !== passwordInput.value) {
                    matchError.classList.remove('hidden');
                } else {
                    matchError.classList.add('hidden');
                }
            };
            confirmInput.addEventListener('input', verifyMatch);
            passwordInput.addEventListener('input', verifyMatch);
        }
    }
});
