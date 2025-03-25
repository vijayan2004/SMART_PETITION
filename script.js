// Function to navigate between pages
function navigateTo(page) {
    window.location.href = page;
}

// Handle Petition Form Submission (Save Data to Local Storage)
document.addEventListener("DOMContentLoaded", function () {
    const petitionForm = document.getElementById("petitionForm");
    if (petitionForm) {
        petitionForm.addEventListener("submit", function (event) {
            event.preventDefault();

            const title = document.getElementById("title").value;
            const description = document.getElementById("description").value;
            const category = document.getElementById("category").value;

            const petition = { title, description, category };
            let petitions = JSON.parse(localStorage.getItem("petitions")) || [];
            petitions.push(petition);
            localStorage.setItem("petitions", JSON.stringify(petitions));

            alert("Petition Created Successfully!");
            navigateTo("dashboard.html");
        });
    }   

    // Display Petitions in View Page
    const petitionList = document.querySelector(".petition-list");
    if (petitionList) {
        let petitions = JSON.parse(localStorage.getItem("petitions")) || [];
        petitionList.innerHTML = petitions.map((petition, index) => `
            <div class="card mb-3">
                <div class="card-body">
                    <h5 class="card-title">${petition.title}</h5>
                    <p class="card-text">${petition.description}</p>
                    <p><strong>Category:</strong> ${petition.category}</p>
                    <button class="btn btn-danger" onclick="deletePetition(${index})">Delete</button>
                </div>
            </div>
        `).join("");
    }
});

// Function to Delete Petition
function deletePetition(index) {
    let petitions = JSON.parse(localStorage.getItem("petitions")) || [];
    petitions.splice(index, 1);
    localStorage.setItem("petitions", JSON.stringify(petitions));
    location.reload();
}
