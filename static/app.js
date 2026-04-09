// Global access for onclick html handlers
let currentPersona = 'admin';

document.addEventListener("DOMContentLoaded", () => {
    
    // --- AUTH SPA LOGIC ---
    const authScreen = document.getElementById('authScreen');
    const osScreen = document.getElementById('osScreen');
    const logoutBtn = document.getElementById('logoutBtn');
    const navPersonaDisplay = document.getElementById('navPersonaDisplay');

    window.loginAs = (role) => {
        currentPersona = role;
        authScreen.style.display = "none";
        osScreen.style.display = "flex";
        
        const modelSelect = document.getElementById('modelSelect');
        modelSelect.innerHTML = ""; // Clear options

        if (role === 'admin') {
            navPersonaDisplay.innerHTML = "<b>Alex</b>";
            document.querySelectorAll('.admin-only').forEach(el => el.style.display = "flex");
            document.querySelectorAll('.standard-only').forEach(el => el.style.display = "none");
            
            // Give Admin full provider list plus capability to add new ones
            modelSelect.innerHTML = `
                <option value="auto">LLM: Auto (Risk-based)</option>
                <option value="openai" selected>LLM: OpenAI (Secure API)</option>
                <option value="gemini">LLM: Gemini (Secure API)</option>
                <option value="local">LLM: Local (Ollama GPU)</option>
            `;
            // Quick mock event listener for adding provider
            const addBtn = document.getElementById('addProviderBtn');
            addBtn.onclick = () => {
                const newProvider = prompt("Enter new Provider Endpoint URL or Name:");
                if(newProvider) {
                    modelSelect.innerHTML += `<option value="${newProvider.toLowerCase()}">LLM: ${newProvider}</option>`;
                    modelSelect.value = newProvider.toLowerCase();
                }
            };
            
        } else {
            navPersonaDisplay.innerHTML = "<b>Jordan</b>";
            document.querySelectorAll('.admin-only').forEach(el => el.style.display = "none");
            document.querySelectorAll('.standard-only').forEach(el => el.style.display = "block");
            
            // Standard User sees typical models. They do not know a router intercepts them if SRDs are found.
            modelSelect.innerHTML = `
                <option value="openai" selected>LLM: OpenAI</option>
                <option value="gemini">LLM: Google Gemini</option>
                <option value="anthropic">LLM: Anthropic</option>
                <option value="local">LLM: Local Engine</option>
            `;
        }    
            // Clean state to ensure Admin-only files are not unintentionally leaked upon logout
            if (activeFileName === "SYSTEM_Intercept_Logs.json") {
                activeFileName = "Q3_Variance_Report.txt";
            }
        }
        
        if (typeof renderFileList === "function") {
            document.getElementById('settingsConsole').style.display = 'none';
            renderFileList();
            loadEditor();
        }
        setTimeout(() => mainEditor.focus(), 100);
    };

    logoutBtn.addEventListener('click', () => {
        osScreen.style.display = "none";
        authScreen.style.display = "flex";
    });

    // --- WORKSPACE & EDITOR STATE ---
    const fileListEl = document.getElementById('fileList');
    const editorTitleInput = document.getElementById('editorTitleInput');
    const mainEditor = document.getElementById('mainEditor');
    const addFileBtn = document.getElementById('addFileBtn');
    const deleteFileBtn = document.getElementById('deleteFileBtn');
    const explorerViewLabel = document.getElementById('explorerViewLabel');
    
    const activityBtns = document.querySelectorAll('.activity-btn');
    
    const MOCK_WORKSPACE_FILES = {
        "Q3_Variance_Report.txt": "EU Branch financial variance report. Net profit fell 4% primarily due to undisclosed leak by Michael Bolton (michael.bolton@securebank.com - SSN 000-00-0000). Total market liability currently assessed at $4.2M.",
        "GDPR_Deletion_Log.csv": "RequestID,Name,Email,Status\n1001,Jane Doe,jane@doe.com,Pending\n1002,John Smith,jsmith@corp.net,Completed",
        "Memo_ProjectPhoenix.txt": "Project strictly confidential. Do not forward. Send updates to compliance-team@corp.com immediately.",
        "SYSTEM_Intercept_Logs.json": '[\n  {"timestamp": "2024-04-09 08:32:15", "user": "Jordan (Sales Rep)", "target_model": "OpenAI (Secure API)", "file": "Q3_Variance_Report.txt", "action": "BLOCKED & REROUTED", "srd_count": 3, "entities": ["Michael Bolton (PERSON)", "michael.bolton@securebank.com (EMAIL)", "000-00-0000 (FINANCE)"]},\n  {"timestamp": "2024-04-09 09:12:05", "user": "Jordan (Sales Rep)", "target_model": "Gemini (Secure API)", "file": "GDPR_Deletion_Log.csv", "action": "BLOCKED & REROUTED", "srd_count": 4, "entities": ["Jane Doe (PERSON)", "jane@doe.com (EMAIL)"]}\n]'
    };

    const MOCK_WORKSPACE_EMAILS = {
        "FWD: Urgent PR Crisis": "From: compliance@securebank.com\nTo: branch_manager@securebank.com\n\nWe need a drafted response immediately regarding the Bolton leak.",
        "EU Audit Notice": "Please gather all records from Q3 to provide to the regulatory board."
    };

    let currentView = "files"; // 'files' or 'emails'
    let activeFileName = null; // Zero context by default

    function getActiveMap() { return currentView === 'files' ? MOCK_WORKSPACE_FILES : MOCK_WORKSPACE_EMAILS; }

    function renderLogViewer(logsArray) {
        const viewer = document.getElementById('logViewer');
        viewer.innerHTML = `<h3>🛡️ SRD Intercept & Enforcement Logs</h3><p style="font-size:0.8rem; color:var(--text-secondary); margin-bottom:10px;">Showing policy routing records for the current session.</p>`;
        
        logsArray.forEach(log => {
            const row = document.createElement('div');
            row.style = "border: 1px solid #cbd5e1; border-radius:8px; padding:12px; font-size:0.85rem; display:flex; flex-direction:column; gap:5px; background:rgba(239, 68, 68, 0.05);";
            row.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <b style="color:var(--text-primary);">${log.file}</b>
                    <span style="font-size:0.75rem; color:var(--text-secondary);">${log.timestamp}</span>
                </div>
                <div>User <b>${log.user}</b> requested execution on <span style="background:#e2e8f0; padding:2px 6px; border-radius:4px;">${log.target_model}</span></div>
                <div style="color:var(--danger); font-weight:600;">⚠️ ${log.action} - ${log.srd_count} SRDs Detected</div>
                <div style="font-family:'Fira Code', monospace; font-size:0.7rem; color:#065f46; background:rgba(16, 185, 129, 0.1); padding:4px 8px; border-radius:4px; margin-top:5px;">
                    Masked: ${log.entities.join(", ")}
                </div>
            `;
            viewer.appendChild(row);
        });
    }

    function renderFileList() {
        fileListEl.innerHTML = "";
        const dataMap = getActiveMap();
        Object.keys(dataMap).forEach(fileName => {
            // Hide Admin system files from standard users
            if (fileName.startsWith("SYSTEM_") && currentPersona !== "admin") return;

            const li = document.createElement('li');
            li.className = `file-item ${fileName === activeFileName ? 'active' : ''}`;
            const icon = currentView === 'files' ? '📄' : '✉️';
            li.innerHTML = `${icon} <span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; pointer-events:none;">${fileName}</span>`;
            
            li.draggable = true;
            li.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('text/plain', JSON.stringify({ type: 'workspace_file', name: fileName, view: currentView }));
                e.dataTransfer.effectAllowed = 'copy';
            });

            li.addEventListener('click', () => {
                if (activeFileName && getActiveMap().hasOwnProperty(activeFileName) && document.getElementById('logViewer').style.display === "none") {
                    getActiveMap()[activeFileName] = mainEditor.value;
                }
                activeFileName = fileName;
                renderFileList();
                loadEditor();
            });
            fileListEl.appendChild(li);
        });
    }

    function loadEditor() {
        const dataMap = getActiveMap();
        const viewer = document.getElementById('logViewer');
        
        if (activeFileName && dataMap.hasOwnProperty(activeFileName)) {
            editorTitleInput.value = activeFileName;
            
            // Check if it's the structured logfile
            if (activeFileName === "SYSTEM_Intercept_Logs.json") {
                mainEditor.style.display = "none";
                viewer.style.display = "flex";
                editorTitleInput.disabled = true;
                deleteFileBtn.style.display = "none";
                try {
                    renderLogViewer(JSON.parse(dataMap[activeFileName]));
                } catch(e) { viewer.innerHTML = "Corrupt Log File"; }
            } else {
                mainEditor.style.display = "block";
                viewer.style.display = "none";
                mainEditor.value = dataMap[activeFileName];
                
                const canEdit = currentPersona === 'admin' || currentView === 'emails';
                mainEditor.disabled = !canEdit;
                editorTitleInput.disabled = !canEdit;
                deleteFileBtn.style.display = "block";
            }
            
            document.querySelector('.editor-title .file-icon').innerText = currentView === 'files' ? '📄' : '✉️';
            document.getElementById("proposalOverlay").style.display = "none";
        } else {
            editorTitleInput.value = "";
            mainEditor.value = "";
            mainEditor.disabled = true;
            editorTitleInput.disabled = true;
            deleteFileBtn.style.display = "none";
            viewer.style.display = "none";
            mainEditor.style.display = "block";
        }
    }

    // Activity Bar Switching
    activityBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const title = e.currentTarget.title;
            const settingsConsole = document.getElementById('settingsConsole');
            
            activityBtns.forEach(b => b.classList.remove('active'));
            e.currentTarget.classList.add('active');
            
            if(title === "Model Configuration") {
                settingsConsole.style.display = "flex";
                return;
            } else if (title === "Settings") {
                settingsConsole.style.display = "none";
                alert("General app preferences menu is under construction.");
                return;
            } else {
                settingsConsole.style.display = "none";
            }
            
            if(activeFileName && getActiveMap().hasOwnProperty(activeFileName)) {
                getActiveMap()[activeFileName] = mainEditor.value;
            }

            if(title === "Local Drive") {
                currentView = "files";
                activeFileName = null;
                explorerViewLabel.innerText = "Local Drive";
            } else {
                currentView = "emails";
                activeFileName = null;
                explorerViewLabel.innerText = "Email Inbox";
            }
            renderFileList();
            loadEditor();
        });
    });

    // React to manual typing in Title or Editor
    editorTitleInput.addEventListener('change', (e) => {
        const newName = e.target.value.trim() || 'Untitled';
        const dataMap = getActiveMap();
        if (newName !== activeFileName) {
            dataMap[newName] = dataMap[activeFileName];
            delete dataMap[activeFileName];
            activeFileName = newName;
            renderFileList();
        }
    });

    mainEditor.addEventListener('input', (e) => {
        if (activeFileName) {
            getActiveMap()[activeFileName] = e.target.value;
        }
    });

    addFileBtn.addEventListener('click', () => {
        const defaultName = currentView === 'files' ? `NewFile_${Date.now()}.txt` : `Draft_${Date.now()}`;
        const newFileName = prompt("Enter a name for the new file:", defaultName);
        if (!newFileName || newFileName.trim() === "") return;
        
        const finalName = newFileName.trim();
        if(!getActiveMap().hasOwnProperty(finalName)) {
            getActiveMap()[finalName] = "";
        }
        activeFileName = finalName;
        renderFileList();
        loadEditor();
        mainEditor.focus();
    });

    const deselectFileBtn = document.getElementById('deselectFileBtn');
    if (deselectFileBtn) {
        deselectFileBtn.addEventListener('click', () => {
            if (activeFileName && getActiveMap().hasOwnProperty(activeFileName)) {
                // save current
                getActiveMap()[activeFileName] = mainEditor.value;
            }
            activeFileName = null; // empty context
            renderFileList();
            loadEditor();
        });
    }

    deleteFileBtn.addEventListener('click', () => {
        if (activeFileName) {
            delete getActiveMap()[activeFileName];
            activeFileName = Object.keys(getActiveMap())[0] || null;
            renderFileList();
            loadEditor();
        }
    });

    // Initialize Workspace Defaults
    renderFileList();
    loadEditor();


    // --- CHAT LOGIC, VOICE MOCK, & DRAG N DROP ---
    const chatWindow = document.getElementById('chatWindow');
    const chatForm = document.getElementById('chatForm');
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    
    // Controls
    const dropZone = document.getElementById('dropZone');
    const modelSelect = document.getElementById('modelSelect');
    const micBtn = document.getElementById('micBtn');

    // Attachments
    const fileAttachment = document.getElementById('fileAttachment');
    const attachmentPreview = document.getElementById('attachmentPreview');
    const attachedFileName = document.getElementById('attachedFileName');
    const removeAttachmentBtn = document.getElementById('removeAttachmentBtn');

    let currentBase64File = null;
    let currentFileName = null;

    // SERVER-BACKED AUDIO RECORDING (DICTATION) -> /api/audio/stt
    let mediaRecorder = null;
    let audioChunks = [];
    let isMicInitializing = false;
    let recordStartTime = 0;

    const stopRecordingCleanly = () => {
        if (mediaRecorder && mediaRecorder.state !== "inactive") {
            mediaRecorder.stop();
        }
    };

    micBtn.addEventListener('mousedown', async (e) => { 
        if (e.button !== 0) return; // ignore right clicks
        if (isMicInitializing || (mediaRecorder && mediaRecorder.state === "recording")) return;
        
        isMicInitializing = true;
        
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];
                
                mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) audioChunks.push(event.data);
                };
                
                mediaRecorder.onstop = async () => {
                    micBtn.classList.remove('listening');
                    chatInput.placeholder = "Processing audio...";
                    
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    const recordDuration = Date.now() - recordStartTime;
                    
                    // Guard against 0-second misclicks or tiny headers
                    if (recordDuration < 600 || audioBlob.size < 1000) {
                        chatInput.placeholder = "Ask AI... (Drop files from workspace here)";
                        stream.getTracks().forEach(track => track.stop());
                        return;
                    }
                    
                    const formData = new FormData();
                    formData.append("audio", audioBlob, "dictation.webm");
                    
                    try {
                        const response = await fetch('/api/audio/stt', { method: 'POST', body: formData });
                        const result = await response.json();
                        if (result.transcript) {
                            chatInput.value += (chatInput.value ? " " : "") + result.transcript;
                            chatInput.dispatchEvent(new Event('input'));
                        } else if (result.detail) {
                            alert("Audio API Error: " + result.detail);
                        }
                    } catch (err) {
                        alert("Dictation Error. Ensure API keys are active.");
                    }
                    chatInput.placeholder = "Ask AI... (Drop files from workspace here)";
                    stream.getTracks().forEach(track => track.stop());
                };
                
                recordStartTime = Date.now();
                mediaRecorder.start();
                micBtn.classList.add('listening'); 
                chatInput.placeholder = "Recording... (Release to Stop)";
            } catch(err) {
                alert("Microphone permission denied or unavailable.");
            } finally {
                isMicInitializing = false;
            }
        }
    });

    micBtn.addEventListener('mouseup', stopRecordingCleanly);
    micBtn.addEventListener('mouseleave', stopRecordingCleanly);

    // DRAG AND DROP LOGIC (Mix OS Native and Browser Native)
    dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        
        // Handle explicit local OS file drops natively
        if (e.dataTransfer.files.length > 0) {
            fileAttachment.files = e.dataTransfer.files;
            fileAttachment.dispatchEvent(new Event('change'));
            return;
        }

        // Handle internal DOM drag (from workspace list)
        const textData = e.dataTransfer.getData('text/plain');
        if (textData) {
            try {
                const parsed = JSON.parse(textData);
                if (parsed.type === 'workspace_file') {
                    const sourceMap = parsed.view === 'files' ? MOCK_WORKSPACE_FILES : MOCK_WORKSPACE_EMAILS;
                    const content = sourceMap[parsed.name];
                    
                    // We mock a base64 encoding locally to simulate a real file attachment for the API
                    currentFileName = parsed.name;
                    currentBase64File = btoa(unescape(encodeURIComponent(content))); 
                    attachedFileName.innerText = currentFileName;
                    attachmentPreview.style.display = "inline-flex";
                }
            } catch (err) {
                // Not standard JSON drop, ignore or treat as text drop
                chatInput.value += textData;
            }
        }
    });

    fileAttachment.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;
        currentFileName = file.name;
        attachedFileName.innerText = file.name;
        attachmentPreview.style.display = "inline-flex";

        const reader = new FileReader();
        reader.onload = (event) => { currentBase64File = event.target.result.split(',')[1]; };
        reader.readAsDataURL(file);
    });

    removeAttachmentBtn.addEventListener('click', () => {
        fileAttachment.value = "";
        currentBase64File = null;
        currentFileName = null;
        attachmentPreview.style.display = "none";
    });

    const clearChatContextBtn = document.getElementById('clearChatContextBtn');
    if(clearChatContextBtn) {
        clearChatContextBtn.addEventListener('click', (e) => {
            e.preventDefault();
            activeFileName = null;
            renderFileList();
            loadEditor();
            chatInput.placeholder = "Ask AI... (Zero context. Drop files here if needed)";
        });
    }

    // Auto-resize textarea
    chatInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });

    const escapeHTML = (str) => new Option(str).innerHTML;
    const scrollToBottom = () => setTimeout(() => chatWindow.scrollTop = chatWindow.scrollHeight, 10);

    const appendUserMessage = (text, implicitlyAttachedFile, explicitlyAttachedFile) => {
        const div = document.createElement('div');
        div.className = "message user-message";
        let contentStr = "";
        
        if (explicitlyAttachedFile) {
            contentStr += `📎 <i>Attached Document: <b>${explicitlyAttachedFile}</b></i>\n\n`;
        } else if (implicitlyAttachedFile) {
            contentStr += `📝 <i>(Implicitly scoped to active file: <b>${implicitlyAttachedFile}</b>)</i>\n\n`;
        }
        
        contentStr += escapeHTML(text);
        div.innerHTML = `<div class="avatar">👤</div><div class="bubble">${contentStr}</div>`;
        chatWindow.appendChild(div);
        scrollToBottom();
    };

    const appendSystemMessagePlaceholder = () => {
        const div = document.createElement('div');
        div.className = "system-wrapper";
        div.style.display = "flex";
        div.style.flexDirection = "column";
        div.style.gap = "5px";
        div.style.width = "100%";
        div.style.animation = "fadeIn 0.3s ease";

        div.innerHTML = `
            <div class="pipeline-step-container"></div>
            <div class="message system-message" style="display: none;">
                <div class="avatar">🛡️</div>
                <div class="bubble"><div class="final-response-text"></div></div>
            </div>
        `;
        chatWindow.appendChild(div);
        scrollToBottom();
        return div;
    };

    const appendPipelineStep = (container, stepData) => {
        if (stepData.step === "hash") return;
        
        // Hide internal compliance logic completely from standard users
        if (currentPersona !== 'admin' && ["srd", "srd_done", "abstract", "abstract_done", "route", "reinject", "judge"].includes(stepData.step)) {
            return;
        }

        const stepWrapper = document.createElement('div');
        stepWrapper.style.display = "flex";
        stepWrapper.style.flexDirection = "column";

        const stepHeader = document.createElement('div');
        stepHeader.className = "pipeline-step";
        
        let icon = "⚙️";
        if (stepData.step === "srd" || stepData.step === "srd_done") icon = "🔍";
        if (stepData.step.includes("abstract")) icon = "🔒";
        if (stepData.step === "route") icon = "🚦";
        if (stepData.step === "model") icon = "🧠";
        if (stepData.step === "reinject") icon = "🔓";
        if (stepData.step === "judge") icon = "⚖️";

        const hasDetails = !!stepData.details;
        const caret = hasDetails ? `<span class="step-caret">▶</span>` : `<span class="step-caret" style="opacity:0;">▶</span>`;
        
        stepHeader.innerHTML = `${caret} <span>${icon}</span> <span>${escapeHTML(stepData.title || "")}</span>`;
        stepWrapper.appendChild(stepHeader);

        if (hasDetails) {
            const detailsDiv = document.createElement('div');
            detailsDiv.className = "step-details";
            detailsDiv.innerText = stepData.details;
            stepWrapper.appendChild(detailsDiv);
            stepHeader.addEventListener('click', () => {
                const isExpanded = detailsDiv.style.display === "block";
                detailsDiv.style.display = isExpanded ? "none" : "block";
                stepHeader.querySelector('.step-caret').classList.toggle('expanded', !isExpanded);
            });
        }
        container.appendChild(stepWrapper);
        scrollToBottom();
    };

    const finalizeSystemMessage = (messageDiv, finalData) => {
        const sysMsgNode = messageDiv.querySelector('.system-message');
        sysMsgNode.style.display = "flex"; 
        const textContainer = messageDiv.querySelector('.final-response-text');
        let outputText = finalData.output;
        
        // --- ADAPTIVE OUTPUT EDIT EXTRACTION ---
        const editRegex = /<EDIT_PROPOSAL>([\s\S]*?)(?:<\/EDIT_PROPOSAL>|$)/i;
        const match = editRegex.exec(outputText);
        
        if (match) {
            const proposedEdit = match[1].trim();
            outputText = outputText.replace(editRegex, "").trim();
            if (!outputText) outputText = "✨ I generated a proposed draft based on your instructions. Please review it in your active workspace!";
            
            // Trigger Diff UI Override
            const proposalOverlay = document.getElementById("proposalOverlay");
            const proposedEditor = document.getElementById("proposedEditor");
            
            mainEditor.disabled = true; // Lock original while reviewing
            proposedEditor.value = proposedEdit;
            proposalOverlay.style.display = "flex";
            
            // Single-use listeners to prevent memory leaks from multiple proposals
            const onAccept = () => {
                getActiveMap()[activeFileName] = proposedEdit;
                mainEditor.value = proposedEdit;
                const canEdit = currentPersona === 'admin' || currentView === 'emails';
                mainEditor.disabled = !canEdit;
                proposalOverlay.style.display = "none";
                document.getElementById('acceptEditBtn').removeEventListener('click', onAccept);
                document.getElementById('rejectEditBtn').removeEventListener('click', onReject);
            };
            const onReject = () => {
                const canEdit = currentPersona === 'admin' || currentView === 'emails';
                mainEditor.disabled = !canEdit;
                proposalOverlay.style.display = "none";
                document.getElementById('acceptEditBtn').removeEventListener('click', onAccept);
                document.getElementById('rejectEditBtn').removeEventListener('click', onReject);
            };
            
            document.getElementById("acceptEditBtn").addEventListener('click', onAccept);
            document.getElementById("rejectEditBtn").addEventListener('click', onReject);
        }

        textContainer.innerText = outputText || "Done.";
        
        const template = document.getElementById('feedbackTemplate');
        const feedbackNode = template.content.cloneNode(true);
        const widgetWrapper = feedbackNode.querySelector('.feedback-widget');
        
        if (finalData.judge && finalData.judge.status !== "APPROVED") {
            const judgeAlert = widgetWrapper.querySelector('.judge-alert');
            judgeAlert.style.display = "block";
            judgeAlert.querySelector('.judge-verdict').innerText = finalData.judge.status;
            judgeAlert.querySelector('.judge-reason').innerText = finalData.judge.reasoning;
        }

        widgetWrapper.querySelectorAll('.feedback-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const rating = e.target.classList.contains('upvote') ? 'UP' : 'DOWN';
                try {
                    await fetch('/feedback', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ request_id: Date.now() % 10000, rating: rating }) });
                    widgetWrapper.querySelector('.feedback-thanks').style.display = "inline";
                } catch(err) {}
            });
        });
        
                
                btn.innerHTML = `🔊 <span style="font-size:0.7rem; font-weight:600;">Playing...</span>`;
                btn.style.color = "var(--accent)";
                currentAudio.play();
                
            } catch(err) {
                alert("TTS Error: " + err.message);
                btn.innerHTML = `🔊 <span style="font-size:0.7rem; font-weight:600;">Play</span>`;
            }
        };
        widgetWrapper.querySelector('.feedback-actions').prepend(readAloudBtn);

        messageDiv.querySelector('.bubble').appendChild(widgetWrapper);
        scrollToBottom();
    };

    // --- SUBMISSION ---
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const rawText = chatInput.value.trim();
        if (!rawText && !currentBase64File) return;

        let implicitContext = null;
        let finalContextString = rawText; 
        
        if (!currentBase64File && activeFileName && getActiveMap()[activeFileName]) {
            implicitContext = activeFileName;
            finalContextString = getActiveMap()[activeFileName];
        }

        appendUserMessage(rawText, implicitContext, currentFileName);
        
        chatInput.value = "";
        chatInput.style.height = 'auto';
        sendBtn.disabled = true;
        
        const capturedFile = currentBase64File;
        const capturedFileName = currentFileName;
        removeAttachmentBtn.click(); // clear UI attach state

        const systemMsgDiv = appendSystemMessagePlaceholder();
        const pipelineContainer = systemMsgDiv.querySelector('.pipeline-step-container');

        try {
            const reqBody = {
                input_type: implicitContext && implicitContext.endsWith(".json") ? "json" : "text",
                content: finalContextString,
                task: rawText, 
                model_pref: modelSelect ? modelSelect.value : "auto", 
                file_name: capturedFileName,
                file_data: capturedFile
            };

            const response = await fetch('/process', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(reqBody) });
            if (!response.ok) throw new Error(`Server error ${response.status}`);

            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n\n");
                buffer = lines.pop(); 
                
                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        try {
                            const data = JSON.parse(line.substring(6));
                            if (data.step === "complete") finalizeSystemMessage(systemMsgDiv, data);
                            else if (data.step === "error") systemMsgDiv.querySelector('.bubble').innerHTML = `<span style="color:var(--danger)">Error: ${data.message}</span>`;
                            else appendPipelineStep(pipelineContainer, data);
                        } catch (err) {}
                    }
                }
            }

        } catch (error) {
            sysMsgNode.style.display = "flex"; 
            systemMsgDiv.querySelector('.bubble').innerText = `Failed to connect: ${error.message}`;
        } finally {
            sendBtn.disabled = false;
            scrollToBottom();
        }
    });

    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if(!sendBtn.disabled) chatForm.dispatchEvent(new Event('submit'));
        }
    });
});
