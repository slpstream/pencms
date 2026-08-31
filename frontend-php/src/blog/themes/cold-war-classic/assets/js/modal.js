document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('image-modal');
    const modalImg = document.getElementById('modal-img');
    const modalCaption = document.getElementById('modal-caption');
    const closeBtn = document.getElementById('modal-close');
    const articleImages = document.querySelectorAll('.article-content img');

    if (!modal || !modalImg || !closeBtn) return;

    const openModal = (img) => {
        modalImg.src = img.src;
        modalImg.alt = img.alt;
        modalCaption.textContent = img.alt || 'IMAGE VIEW';
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    };

    const closeModal = () => {
        modal.classList.remove('active');
        document.body.style.overflow = '';
        // Small delay to clear src after transition
        setTimeout(() => {
            modalImg.src = '';
        }, 300);
    };

    articleImages.forEach(img => {
        img.addEventListener('click', (e) => {
            e.preventDefault();
            openModal(img);
        });
    });

    closeBtn.addEventListener('click', closeModal);
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal || e.target.closest('.modal-close')) {
            closeModal();
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.classList.contains('active')) {
            closeModal();
        }
    });
});
