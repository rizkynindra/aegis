function openPhoto(src) {
    const modal = document.getElementById('photoModal');
    const modalImg = document.getElementById('modalImg');
    if (modal && modalImg) {
        modalImg.src = src;
        modal.classList.add('active');
        modal.style.display = 'flex';
    }
}

function toggleCategorySelect(role) {
    const catSelect = document.getElementById('category-select');
    if (catSelect) {
        if (role === 'disaster') {
            catSelect.style.display = 'block';
            catSelect.required = true;
        } else {
            catSelect.style.display = 'none';
            catSelect.required = false;
        }
    }
}

// Close modal on click outside image
document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('photoModal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
                modal.style.display = 'none';
            }
        });
    }
});
