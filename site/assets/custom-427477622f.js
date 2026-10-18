document.addEventListener("DOMContentLoaded", function () {
    const sidebarSwiper = new Swiper(".sidebarSwiper", {
        slidesPerView: "auto",
        spaceBetween: 10,
        freeMode: {
            enabled: true,
            sticky: true,
            momentumBounce: false,
        },
        grabCursor: true,
        navigation: {
            nextEl: ".swiper-button-next",
            prevEl: ".swiper-button-prev",
        },
        breakpoints: {
            320: {
                slidesPerView: 2,
                spaceBetween: 2,
            },
            480: {
                slidesPerView: 3,
                spaceBetween: 7,
            },
            768: {
                slidesPerView: "auto",
                spaceBetween: 10,
            },
        },
        on: {
            init: function () {
                const swiper = this;
                const swiperWidth = swiper.width;
                const slidesWidth = swiper.slides.reduce((total, slide) => total + slide.offsetWidth + swiper.params.spaceBetween, 0);
                const maxTranslate = -(slidesWidth - swiperWidth);

                swiper.maxTranslate = () => maxTranslate;
                swiper.minTranslate = () => 0;

                // Dodajemo nevidljivi stop element
                const stopElement = document.createElement("div");
                stopElement.className = "swiper-slide-invisible-stop";
                stopElement.style.width = swiperWidth * 0.4 + "px"; // 40% širine vidljivog prostora
                swiper.el.querySelector(".swiper-wrapper").appendChild(stopElement);
            },
            beforeTransitionStart: function () {
                const swiper = this;
                const totalSlides = swiper.slides.length - 1; // Oduzimamo stop element
                const lastVisibleIndex = totalSlides - 2;

                if (swiper.activeIndex >= lastVisibleIndex) {
                    swiper.setTranslate(swiper.maxTranslate());
                    swiper.allowSlideNext = false;
                }
            },
            touchEnd: function () {
                const swiper = this;
                const totalSlides = swiper.slides.length - 1;
                const lastVisibleIndex = totalSlides - 2;

                if (swiper.activeIndex >= lastVisibleIndex) {
                    swiper.slideTo(lastVisibleIndex, 300, false);
                }
            },
            fromEdge: function () {
                const swiper = this;
                swiper.allowSlideNext = true;
            },
        },
    });
});

// Float Admin
(function ($) {
    "use strict";

    $.fn.launchBtn = function (options) {
        var mainBtn, panel, clicks, settings, launchPanelAnim, closePanelAnim, openPanel, boxClick;

        mainBtn = $(".radeAdminBtn");
        panel = $(".radeCard");
        clicks = 0;

        //default settings
        settings = $.extend(
            {
                openDuration: 600,
                closeDuration: 200,
                rotate: true,
            },
            options
        );

        //Open panel animation
        launchPanelAnim = function () {
            panel.animate(
                {
                    opacity: "toggle",
                    height: "toggle",
                },
                settings.openDuration
            );
        };

        //Close panel animation
        closePanelAnim = function () {
            panel.animate(
                {
                    opacity: "hide",
                    height: "hide",
                },
                settings.closeDuration
            );
        };

        //Open panel and rotate icon
        openPanel = function (e) {
            if (clicks === 0) {
                if (settings.rotate) {
                    $(this).removeClass("rotateBackward").toggleClass("rotateForward");
                }

                launchPanelAnim();
                clicks++;
            } else {
                if (settings.rotate) {
                    $(this).removeClass("rotateForward").toggleClass("rotateBackward");
                }

                closePanelAnim();
                clicks--;
            }
            e.preventDefault();
            return false;
        };

        //Allow clicking in panel
        boxClick = function (e) {
            e.stopPropagation();
        };

        //Main button click
        mainBtn.on("click", openPanel);

        //Prevent closing panel when clicking inside
        panel.click(boxClick);

        //Click away closes panel when clicked in document
        $(document).click(function () {
            closePanelAnim();
            if (clicks === 1) {
                mainBtn.removeClass("rotateForward").toggleClass("rotateBackward");
            }
            clicks = 0;
        });
    };

    // Inicijalizacija nakon što je DOM spreman
    $(document).ready(function () {
        $(".radeContainer").launchBtn({
            openDuration: 400,
            closeDuration: 300,
            rotate: true,
        });
    });
})(jQuery);

$(document).ready(function () {
    $("#liveToast").toast("show");

    $("#btnEmailVerificationClose").on("click", function () {
        $("#liveToast").toast("hide");
    });
});

/*
function initColorPicker() {
    const colorInputs = document.querySelectorAll('.color-picker-grid input[type="color"]');

    // Load saved colors
    colorInputs.forEach((input) => {
        const varName = input.dataset.var;
        const savedColor = localStorage.getItem(`theme-${varName}`);
        if (savedColor) {
            document.documentElement.style.setProperty(varName, savedColor);
            input.value = savedColor;
        }
    });

    // Handle color changes
    colorInputs.forEach((input) => {
        input.addEventListener("change", (e) => {
            const varName = e.target.dataset.var;
            const newColor = e.target.value;
            document.documentElement.style.setProperty(varName, newColor);
        });
    });

    // Save colors
    $("#saveThemeColors").on("click", function (e) {
        e.preventDefault();

        // Pripremi podatke za slanje
        let colors = {};
        colorInputs.forEach((input) => {
            colors[input.dataset.var] = input.value;
        });

        // Prikaži loading stanje
        $(this).prop("disabled", true).html('<i class="fas fa-spinner fa-spin"></i> Saving...');

        // Pošalji na server
        $.ajax({
            url: "templates/radisic/save_colors.php", // Prilagodite putanju prema vašoj strukturi
            method: "POST",
            data: {
                colors: colors,
                token: csrfToken,
            },
            dataType: "json",
            success: function (response) {
                if (response.success) {
                    alert("Colors saved successfully!");
                } else {
                    alert("Error saving colors: " + response.message);
                }
            },
            error: function () {
                alert("Error saving colors. Please try again.");
            },
            complete: function () {
                $("#saveThemeColors").prop("disabled", false).html("Save Colors");
            },
        });
    });

    // Reset colors
    $("#resetThemeColors").on("click", function (e) {
        e.preventDefault();
        if (confirm("Are you sure you want to reset all colors to default?")) {
            $.ajax({
                url: "templates/radisic/reset_colors.php",
                method: "POST",
                data: { token: csrfToken },
                dataType: "json",
                success: function (response) {
                    if (response.success) {
                        localStorage.clear();
                        location.reload();
                    } else {
                        alert("Error resetting colors: " + response.message);
                    }
                },
            });
        }
    });
}

// Initialize when document is ready
$(document).ready(function () {
    if ($(".radeContainer").length) {
        initColorPicker();
    }
});
*/
