document.addEventListener('DOMContentLoaded', function() {
    // Check if Cleave is available
    if (typeof Cleave === 'undefined') {
        console.warn('Cleave.js library not loaded');
        return;
    }

    // Initialize Cleave inputs only if elements exist
    const cpfElement = document.getElementById('cpf');
    if (cpfElement) {
        const cpfInput = new Cleave('#cpf', {
            delimiters: ['.', '.', '-'],
            blocks: [3, 3, 3, 2],
            numericOnly: true
        });
    }

    const phoneElement = document.getElementById('phone');
    if (phoneElement) {
        const phoneInput = new Cleave('#phone', {
            delimiters: ['(', ')', ' ', '-'],
            blocks: [0, 2, 5, 4],
            numericOnly: true
        });
    }

    const zipElement = document.getElementById('zip_code');
    if (zipElement) {
        const zipInput = new Cleave('#zip_code', {
            delimiters: ['-'],
            blocks: [5, 3],
            numericOnly: true
        });
    }

    function validateCPF(cpf) {
        cpf = cpf.replace(/[^\d]/g, '');
        if (cpf.length !== 11) return false;

        // CPF validation algorithm
        let sum = 0;
        for (let i = 0; i < 9; i++) {
            sum += parseInt(cpf.charAt(i)) * (10 - i);
        }
        let digit = 11 - (sum % 11);
        if (digit >= 10) digit = 0;
        if (digit !== parseInt(cpf.charAt(9))) return false;

        sum = 0;
        for (let i = 0; i < 10; i++) {
            sum += parseInt(cpf.charAt(i)) * (11 - i);
        }
        digit = 11 - (sum % 11);
        if (digit >= 10) digit = 0;
        if (digit !== parseInt(cpf.charAt(10))) return false;

        return true;
    }

    function validateEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    }

    // Handle registration form
    const registrationForm = document.querySelector('#registration-form');
    if (registrationForm) {
        registrationForm.addEventListener('submit', function(e) {
            e.preventDefault();

            const cpf = document.getElementById('cpf');
            const email = document.getElementById('email');

            if (cpf && !validateCPF(cpf.value)) {
                alert('CPF inválido. Por favor, verifique.');
                return;
            }

            if (email && !validateEmail(email.value)) {
                alert('Email inválido. Por favor, verifique.');
                return;
            }

            // Show loading indicator if it exists
            const loadingElement = document.getElementById('loading');
            if (loadingElement) {
                loadingElement.classList.remove('hidden');
            }

            // Submit the form
            registrationForm.submit();
        });
    }
});