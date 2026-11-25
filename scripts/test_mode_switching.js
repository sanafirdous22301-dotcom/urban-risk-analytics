const fs = require('fs');
const path = require('path');

// Verify that frontend/js/script.js contains the exact mode handling logic
const scriptCode = fs.readFileSync(path.join(__dirname, '../frontend/js/script.js'), 'utf8');

console.log('=== VERIFYING FRONTEND SCRIPT MODE LOGIC ===');

// 1. Check mode-aware executeAssessment
if (!scriptCode.includes('if (currentAssessmentMode === "current") {') || !scriptCode.includes('renderCurrentConditionsAssessment();')) {
    throw new Error('executeAssessment is not mode-aware!');
}
console.log('PASS: executeAssessment is mode-aware');

// 2. Check Card 1 dynamic titles
if (!scriptCode.includes('setText("homePriorityTitleLabel", "Integrated Urban Priority (IUPS)")')) {
    throw new Error('Historical mode does not set Card 1 title to Integrated Urban Priority (IUPS)!');
}
if (!scriptCode.includes('setText("homePriorityTitleLabel", "Current Operational Screening Priority")')) {
    throw new Error('Current mode does not set Card 1 title to Current Operational Screening Priority!');
}
console.log('PASS: Card 1 dynamic titles present');

// 3. Check formula subnotes
if (!scriptCode.includes('Historical baseline (Flood 35%, Heat 35%, Infra 15%, Road 15%)')) {
    throw new Error('Historical 35/35/15/15 subnote missing!');
}
if (!scriptCode.includes('Real-time screening (Heat 40%, Rain 25%, Infra 20%, Road 15%)')) {
    throw new Error('Current 40/25/20/15 subnote missing!');
}
console.log('PASS: Both mode formulas clearly distinguished in subnotes');

// 4. Check Right Panel Eyebrows & Score labels
if (!scriptCode.includes('setText("analysisEyebrow", "HISTORICAL IUPS ASSESSMENT")')) {
    throw new Error('Historical analysis eyebrow missing!');
}
if (!scriptCode.includes('setText("analysisEyebrow", "CURRENT OPERATIONAL SCREENING")')) {
    throw new Error('Current analysis eyebrow missing!');
}
console.log('PASS: Right panel eyebrows distinguished between modes');

// 5. Verify index.html has homePriorityTitleLabel ID
const htmlCode = fs.readFileSync(path.join(__dirname, '../frontend/html/index.html'), 'utf8');
if (!htmlCode.includes('id="homePriorityTitleLabel"')) {
    throw new Error('homePriorityTitleLabel ID missing in index.html!');
}
if (htmlCode.includes('Local Map Cache')) {
    throw new Error('Technical label Local Map Cache still present in index.html!');
}
console.log('PASS: HTML IDs and technical label cleanup verified');

console.log('>>> ALL FRONTEND SCRIPT & HTML CHECKS PASSED! <<<');
