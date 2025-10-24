function mapDriveImages() {
  const FOLDER_ID = '1fIRR9rQQla7-d48r12yLMELD3VAXifHx'; // Replace with your folder ID
  const SHEET_NAME = 'Data'; // Replace with your actual sheet name
  const EVENT_ID_COLUMN = 14; // Column N (Backend Event Id)
  const STEPZERO_COLUMN = 20; // Column T (Event Hero Enhanced Image - StepZero URLs)
  const OUTPUT_COLUMN = 22; // Column V (Output Spotlight Image)
  const START_ROW = 3; // Your data starts at row 3
  
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
  
  // Helper function to extract UUID from StepZero URL
  function extractUUID(url) {
    if (!url || url === '') return null;
    // Try specific image_editing path first (more precise)
    const imageEditingMatch = url.match(/\/image_editing\/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})\//i);
    if (imageEditingMatch) {
      return imageEditingMatch[1];
    }
    // Fallback to generic UUID extraction
    const genericMatch = url.match(/\/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\//);
    return genericMatch ? genericMatch[1] : null;
  }
  
  // Try to get the folder
  let folder;
  try {
    folder = DriveApp.getFolderById(FOLDER_ID);
    Logger.log(`✓ Folder found: ${folder.getName()}`);
  } catch (e) {
    SpreadsheetApp.getUi().alert('Error: Invalid Folder ID. Please check the FOLDER_ID in the script.');
    return;
  }
  
  // Get all files in the folder
  const files = folder.getFiles();
  const fileMap = {};
  let fileCount = 0;
  
  Logger.log('--- Scanning Google Drive folder ---');
  
  while (files.hasNext()) {
    const file = files.next();
    const fileName = file.getName();
    const fileId = file.getId();
    fileMap[fileName] = fileId;
    fileCount++;
    Logger.log(`${fileCount}. ${fileName} → ${fileId}`);
  }
  
  Logger.log(`\n✓ Total files found: ${fileCount}\n`);
  
  if (fileCount === 0) {
    SpreadsheetApp.getUi().alert('Error: No files found in the Drive folder. Check folder permissions.');
    return;
  }
  
  // Get data from sheet
  const lastRow = sheet.getLastRow();
  Logger.log(`Last row in sheet: ${lastRow}`);
  
  if (lastRow < START_ROW) {
    SpreadsheetApp.getUi().alert('Error: No data found in the sheet.');
    return;
  }
  
  // Get Event ID (column N), StepZero URLs (column T), and Output column (column V) data
  const eventIdData = sheet.getRange(START_ROW, EVENT_ID_COLUMN, lastRow - START_ROW + 1, 1).getDisplayValues();
  const stepzeroData = sheet.getRange(START_ROW, STEPZERO_COLUMN, lastRow - START_ROW + 1, 1).getDisplayValues();
  const outputData = sheet.getRange(START_ROW, OUTPUT_COLUMN, lastRow - START_ROW + 1, 1).getValues();
  
  Logger.log(`\n--- Processing rows ---\n`);
  
  // Prepare output links (only for blank rows)
  const outputLinks = [];
  let foundCount = 0;
  let notFoundCount = 0;
  let skippedCount = 0;
  let stepzeroFoundCount = 0;
  let eventIdFoundCount = 0;
  
  for (let i = 0; i < eventIdData.length; i++) {
    const eventId = String(eventIdData[i][0]).trim();
    const stepzeroUrl = String(stepzeroData[i][0]).trim();
    const existingValue = String(outputData[i][0]).trim();
    const rowNum = START_ROW + i;
    
    // Skip if row already has a value in column V
    if (existingValue && existingValue !== '' && existingValue !== 'NOT FOUND') {
      outputLinks.push([existingValue]); // Keep existing value
      skippedCount++;
      Logger.log(`Row ${rowNum}: Skipped (already has value)`);
      continue;
    }
    
    let found = false;
    
    // Priority 1: Try StepZero UUID mapping if URL exists in Column T
    if (stepzeroUrl && stepzeroUrl !== '' && stepzeroUrl !== 'null') {
      const uuid = extractUUID(stepzeroUrl);
      if (uuid) {
        Logger.log(`\nRow ${rowNum}: Processing StepZero UUID = ${uuid}`);
        const stepzeroFileName = `${uuid}.jpeg`;
        
        if (fileMap[stepzeroFileName]) {
          const fileId = fileMap[stepzeroFileName];
          const directLink = `https://drive.google.com/file/d/${fileId}/view`;
          outputLinks.push([directLink]);
          foundCount++;
          stepzeroFoundCount++;
          found = true;
          Logger.log(`  ✓ FOUND (StepZero): ${stepzeroFileName} → ${directLink}`);
        } else {
          Logger.log(`  ⊘ StepZero file not found: ${stepzeroFileName}`);
        }
      } else {
        Logger.log(`\nRow ${rowNum}: Could not extract UUID from StepZero URL`);
      }
    }
    
    // Priority 2: Fall back to Event ID mapping if StepZero not found
    if (!found && eventId && eventId !== '' && eventId !== 'null') {
      Logger.log(`\nRow ${rowNum}: Falling back to Event ID = ${eventId}`);
      
      // Try multiple file name variations
      const variations = [
        `${eventId}.jpeg`,
        `${eventId}.jpg`,
        `${eventId}.JPEG`,
        `${eventId}.JPG`,
        `${eventId}.png`,
        `${eventId}.PNG`
      ];
      
      for (let variation of variations) {
        if (fileMap[variation]) {
          const fileId = fileMap[variation];
          const directLink = `https://drive.google.com/file/d/${fileId}/view`;
          outputLinks.push([directLink]);
          foundCount++;
          eventIdFoundCount++;
          found = true;
          Logger.log(`  ✓ FOUND (Event ID): ${variation} → ${directLink}`);
          break;
        }
      }
      
      if (!found) {
        Logger.log(`  ✗ NOT FOUND: Tried ${variations.join(', ')}`);
      }
    }
    
    // If nothing found, mark as NOT FOUND
    if (!found) {
      outputLinks.push(['NOT FOUND']);
      notFoundCount++;
    }
  }
  
  // Write links to the Output column (images)
  sheet.getRange(START_ROW, OUTPUT_COLUMN, outputLinks.length, 1).setValues(outputLinks);

  Logger.log(`\n--- Image Summary ---`);
  Logger.log(`✓ Total Found: ${foundCount}`);
  Logger.log(`  ├─ StepZero (UUID): ${stepzeroFoundCount}`);
  Logger.log(`  └─ Event ID: ${eventIdFoundCount}`);
  Logger.log(`✗ Not Found: ${notFoundCount}`);
  Logger.log(`→ Skipped (already filled): ${skippedCount}`);
  Logger.log(`Total rows: ${eventIdData.length}`);

  // --- VIDEO MAPPING ---
  const VIDEO_OUTPUT_COLUMN = 23; // Column W for video spotlight links
  const videoOutputLinks = [];
  for (let i = 0; i < eventIdData.length; i++) {
    const eventId = String(eventIdData[i][0]).trim();
    // skip blank event IDs
    if (!eventId || eventId === '' || eventId === 'null') {
      videoOutputLinks.push(['']);
      continue;
    }
    // Try video file variations
    const videoVariations = [
      `${eventId}.mp4`,
      `${eventId}.MP4`,
    ];
    let foundVideo = false;
    for (let variation of videoVariations) {
      if (fileMap[variation]) {
        const fileId = fileMap[variation];
        const directLink = `https://drive.google.com/file/d/${fileId}/view`;
        videoOutputLinks.push([directLink]);
        foundVideo = true;
        break;
      }
    }
    if (!foundVideo) {
      videoOutputLinks.push(['NOT FOUND']);
    }
  }
  // Write video links to Column W
  sheet.getRange(START_ROW, VIDEO_OUTPUT_COLUMN, videoOutputLinks.length, 1).setValues(videoOutputLinks);

  SpreadsheetApp.getActiveSpreadsheet().toast(
    `Done! Found: ${foundCount} (StepZero: ${stepzeroFoundCount}, Event ID: ${eventIdFoundCount}), Not Found: ${notFoundCount}, Skipped: ${skippedCount}`,
    'Mapping Complete',
    5
  );
}