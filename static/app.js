document.addEventListener("DOMContentLoaded", () => {
    
    // Check connection implicitly assuming if page loaded, server is there.
    document.getElementById('backendStatus').innerText = "V1 API Connected";

    const form = document.getElementById('processForm');
    const mockBtn = document.getElementById('mockEmailBtn');
    
    // UI Elements
    const cards = [
        document.getElementById('step1'), 
        document.getElementById('step2'), 
        document.getElementById('step3'), 
        document.getElementById('step4')
    ];
    const connections = document.querySelectorAll('.pipeline-connection');
    
    const resultTexts = {
        srd: document.getElementById('srdResult'),
        route: document.getElementById('routeResult'),
        model: document.getElementById('modelResult'),
        judge: document.getElementById('judgeResult')
    };

    const finalOutput = document.getElementById('finalOutput');
    const riskBadge = document.getElementById('riskBadge');
    const routeText = document.getElementById('routeText');
    
    const feedbackWidget = document.getElementById('feedbackWidget');

    // Fill mocked data
    mockBtn.addEventListener('click', () => {
        document.getElementById('taskInput').value = "Extract key action items and summarize risk.";
        document.getElementById('contentInput').value = `To: compliance-team@corp.com\nFrom: john.doe@securebank.com\nSubject: Project Phoenix Delays\n\nHi team, we need to report that customer Jane Smith (SSN: 000-00-0000) has requested a full GDPR deletion. Also, the Q3 revenues from the EU branch leaked inadvertently by Michael Bolton to public forums. Please advise.`;
    });

    const resetPipeline = () => {
        cards.forEach(c => c.classList.remove('active'));
        connections.forEach(c => c.classList.remove('active'));
        Object.values(resultTexts).forEach(r => r.innerText = "Waiting...");
        finalOutput.innerText = "Interrogating model...";
        riskBadge.innerText = "-";
        riskBadge.className = "meta-value";
        routeText.innerText = "-";
        feedbackWidget.style.display = "none";
        document.getElementById('feedbackThanks').style.display = "none";
    };

    const animatePipeline = async (data) => {
        // Step 1: SRD Detection
        cards[0].classList.add('active');
        resultTexts.srd.innerText = `Detected ${data.srd_count} SRD entities. Processing abstraction...`;
        await sleep(800);

        // Step 2: Routing
        connections[0].classList.add('active');
        cards[1].classList.add('active');
        resultTexts.route.innerText = `Risk Level: ${data.risk_level}. Policy dictates: ${data.route} route.`;
        await sleep(800);

        // Step 3: Model
        connections[1].classList.add('active');
        cards[2].classList.add('active');
        const modelName = data.model_used === "local_ollama" ? "Local Llama" : "External Proprietary API";
        resultTexts.model.innerText = `Sending anonymized context to ${modelName}...`;
        await sleep(1500);

        // Step 4: Judge
        connections[2].classList.add('active');
        cards[3].classList.add('active');
        resultTexts.judge.innerText = `Judge verdict: ${data.judge.status}`;
        
        // Show Final details
        finalOutput.innerText = data.output;
        
        routeText.innerText = data.route;
        riskBadge.innerText = data.risk_level;
        riskBadge.classList.add(`badge-${data.risk_level.toLowerCase()}`);

        document.getElementById('judgeVerdict').innerText = data.judge.status;
        document.getElementById('judgeReason').innerText = data.judge.reasoning;
        feedbackWidget.style.display = "block";
    };

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const task = document.getElementById('taskInput').value;
        const content = document.getElementById('contentInput').value;
        
        const submitBtn = document.getElementById('submitBtn');
        const spinner = submitBtn.querySelector('.loader-spinner');
        const btnText = submitBtn.querySelector('span');

        resetPipeline();
        
        // Setup Loading state
        submitBtn.disabled = true;
        spinner.style.display = "inline-block";
        btnText.innerText = "Processing...";

        try {
            const reqBody = {
                input_type: "text",
                content: content,
                task: task,
                model_pref: "auto"
            };

            const response = await fetch('/process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(reqBody)
            });

            if (!response.ok) {
                throw new Error("Server error " + response.status);
            }

            const data = await response.json();
            
            // Animate revealing the timeline based on data
            await animatePipeline(data);

        } catch (error) {
            console.error(error);
            finalOutput.innerText = `Failed to process request: ${error.message}`;
        } finally {
            submitBtn.disabled = false;
            spinner.style.display = "none";
            btnText.innerText = "Process Payload";
        }
    });

    // Handle Feedback
    document.querySelectorAll('.feedback-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const rating = e.target.getAttribute('data-rating');
            try {
                // In a real app we'd need the actual DB request ID, here we mock it to 1 for MVP UI demo
                await fetch('/feedback', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ request_id: 1, rating: rating })
                });
                document.getElementById('feedbackThanks').style.display = "block";
            } catch (err) {
                console.error("Feedback failed", err);
            }
        });
    });

    const sleep = (ms) => new Promise(r => setTimeout(r, ms));
});
