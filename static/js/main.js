// main.js — students will add JavaScript here as features are built

// ------------------------------------------------------------------ //
// "See how it works" video modal (landing page)                       //
// ------------------------------------------------------------------ //
(function () {
    const trigger = document.getElementById("how-it-works-btn");
    const modal = document.getElementById("video-modal");
    if (!trigger || !modal) return; // not on the landing page

    const iframe = modal.querySelector("iframe");
    const closeBtn = modal.querySelector(".video-modal-close");
    const videoSrc = modal.dataset.videoSrc;

    function openModal() {
        iframe.src = videoSrc; // load (and autoplay) only when opened
        modal.hidden = false;
        document.body.classList.add("modal-open");
        closeBtn.focus();
        document.addEventListener("keydown", onKeydown);
    }

    function closeModal() {
        modal.hidden = true;
        // Removing the src unloads the player, so the video stops completely.
        iframe.src = "";
        document.body.classList.remove("modal-open");
        document.removeEventListener("keydown", onKeydown);
        trigger.focus();
    }

    function onKeydown(event) {
        if (event.key === "Escape") closeModal();
    }

    trigger.addEventListener("click", openModal);
    closeBtn.addEventListener("click", closeModal);

    // Clicks on the dark backdrop (outside the dialog box) close the modal.
    modal.addEventListener("click", function (event) {
        if (event.target === modal) closeModal();
    });
})();
