/* A "Generál" gomb a csoport meghívókódja mellé az adminban.
 *
 * A kódot itt, a böngészőben állítjuk elő, hogy a tanár mentés előtt már
 * fel tudja olvasni. Az egyediséget a mentés ellenőrzi: a mező unique, és
 * üresen hagyva a szerver maga generál egy szabadat.
 */
(function () {
    "use strict";

    // Nincs benne 0/O és 1/I: a diákok ezeket keverik össze másoláskor.
    const ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
    const LENGTH = 6;

    function newCode() {
        const numbers = new Uint32Array(LENGTH);
        window.crypto.getRandomValues(numbers);

        let code = "";

        for (const number of numbers) {
            code += ALPHABET[number % ALPHABET.length];
        }

        return code;
    }

    document.addEventListener("DOMContentLoaded", function () {
        const field = document.getElementById("id_invite_code");

        if (field === null) {
            return;
        }

        const button = document.createElement("button");

        button.type = "button";
        button.textContent = "Generál";
        button.className = "resolve-invite-code-button";

        button.addEventListener("click", function () {
            field.value = newCode();
            field.focus();
        });

        field.insertAdjacentElement("afterend", button);
    });
})();
