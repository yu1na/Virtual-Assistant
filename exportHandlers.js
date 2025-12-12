/**
 * Electron 내보내기 핸들러
 * PDF 및 CSV 내보내기 기능 제공
 */

const { ipcMain, dialog, BrowserWindow } = require('electron');
const fs = require('fs');
const path = require('path');

/**
 * PDF 내보내기 핸들러
 * webContents.printToPDF()를 사용하여 현재 창을 PDF로 변환
 */
ipcMain.handle('export-pdf', async (event) => {
  console.log('📄 PDF 내보내기 요청 받음');
  
  try {
    // 요청을 보낸 창 가져오기
    const win = BrowserWindow.fromWebContents(event.sender);
    if (!win) {
      throw new Error('창을 찾을 수 없습니다.');
    }
    
    // 저장 경로 선택 대화창
    const { filePath, canceled } = await dialog.showSaveDialog(win, {
      title: 'PDF 저장',
      defaultPath: `보고서_${new Date().toISOString().split('T')[0]}.pdf`,
      filters: [
        { name: 'PDF 파일', extensions: ['pdf'] }
      ]
    });
    
    if (canceled || !filePath) {
      console.log('📄 PDF 내보내기 취소됨');
      return { success: false, message: '취소되었습니다.' };
    }
    
    // 파일 경로 정규화 (경로 조작 공격 방지)
    const normalizedPath = path.normalize(filePath);
    console.log('📄 PDF 저장 경로:', normalizedPath);
    
    // PDF 생성 옵션 (Electron의 Chromium PDF 엔진 사용)
    const pdfOptions = {
      landscape: false,           // 세로 방향
      printBackground: true,      // 배경 색상 및 이미지 인쇄
      marginsType: 0,             // 여백 없음 (0: default, 1: none, 2: minimum)
      pageSize: 'A4',             // A4 용지 크기
      printSelectionOnly: false   // 전체 페이지 인쇄
    };
    
    // webContents.printToPDF()로 PDF 생성
    console.log('📄 PDF 생성 중...');
    const pdfBuffer = await win.webContents.printToPDF(pdfOptions);
    
    // 파일 저장
    fs.writeFileSync(normalizedPath, pdfBuffer);
    console.log('✅ PDF 저장 완료:', normalizedPath);
    
    return { 
      success: true, 
      message: 'PDF가 저장되었습니다.',
      filePath: normalizedPath 
    };
    
  } catch (error) {
    console.error('❌ PDF 내보내기 오류:', error);
    return { 
      success: false, 
      message: error.message || 'PDF 내보내기 중 오류가 발생했습니다.' 
    };
  }
});

/**
 * CSV 내보내기 핸들러
 * 2차원 배열을 CSV 형식으로 변환하여 저장
 */
ipcMain.handle('export-csv', async (event, data) => {
  console.log('📊 CSV 내보내기 요청 받음');
  
  try {
    // 입력 검증
    if (!data || !Array.isArray(data) || data.length === 0) {
      throw new Error('유효한 데이터가 없습니다.');
    }
    
    // 요청을 보낸 창 가져오기
    const win = BrowserWindow.fromWebContents(event.sender);
    if (!win) {
      throw new Error('창을 찾을 수 없습니다.');
    }
    
    // 저장 경로 선택 대화창
    const { filePath, canceled } = await dialog.showSaveDialog(win, {
      title: 'CSV 저장',
      defaultPath: `보고서_데이터_${new Date().toISOString().split('T')[0]}.csv`,
      filters: [
        { name: 'CSV 파일', extensions: ['csv'] }
      ]
    });
    
    if (canceled || !filePath) {
      console.log('📊 CSV 내보내기 취소됨');
      return { success: false, message: '취소되었습니다.' };
    }
    
    // 파일 경로 정규화 (경로 조작 공격 방지)
    const normalizedPath = path.normalize(filePath);
    console.log('📊 CSV 저장 경로:', normalizedPath);
    
    // CSV 문자열 변환
    // RFC 4180 표준 준수: 쉼표(,) 포함 시 따옴표로 감싸기
    const csvContent = data.map(row => {
      return row.map(cell => {
        const cellStr = String(cell || '');
        // 쉼표, 따옴표, 줄바꿈이 포함되면 따옴표로 감싸기
        if (cellStr.includes(',') || cellStr.includes('"') || cellStr.includes('\n')) {
          // 따옴표는 두 개로 이스케이프
          return `"${cellStr.replace(/"/g, '""')}"`;
        }
        return cellStr;
      }).join(',');
    }).join('\n');
    
    // BOM 추가 (Excel에서 한글 깨짐 방지)
    const bom = '\uFEFF';
    const csvWithBom = bom + csvContent;
    
    // 파일 저장 (UTF-8 with BOM)
    fs.writeFileSync(normalizedPath, csvWithBom, 'utf8');
    console.log('✅ CSV 저장 완료:', normalizedPath);
    
    return { 
      success: true, 
      message: 'CSV가 저장되었습니다.',
      filePath: normalizedPath,
      rowCount: data.length 
    };
    
  } catch (error) {
    console.error('❌ CSV 내보내기 오류:', error);
    return { 
      success: false, 
      message: error.message || 'CSV 내보내기 중 오류가 발생했습니다.' 
    };
  }
});

/**
 * 정적 HTML 보고서에서 PDF 내보내기 핸들러
 * HTML 문자열을 받아서 PDF로 변환
 */
ipcMain.handle('export-pdf-from-static', async (event, data) => {
  console.log('📄 정적 HTML에서 PDF 내보내기 요청 받음');
  
  try {
    const { html, title } = data;
    
    if (!html) {
      throw new Error('HTML 데이터가 없습니다.');
    }
    
    // 요청을 보낸 창 가져오기
    const win = BrowserWindow.fromWebContents(event.sender);
    if (!win) {
      throw new Error('창을 찾을 수 없습니다.');
    }
    
    // 저장 경로 선택 대화창
    const { filePath, canceled } = await dialog.showSaveDialog(win, {
      title: 'PDF 저장',
      defaultPath: `${title || '보고서'}_${new Date().toISOString().split('T')[0]}.pdf`,
      filters: [
        { name: 'PDF 파일', extensions: ['pdf'] }
      ]
    });
    
    if (canceled || !filePath) {
      console.log('📄 PDF 내보내기 취소됨');
      return { success: false, message: '취소되었습니다.' };
    }
    
    // 파일 경로 정규화
    const normalizedPath = path.normalize(filePath);
    console.log('📄 PDF 저장 경로:', normalizedPath);
    
    // PDF 생성 옵션
    const pdfOptions = {
      landscape: false,
      printBackground: true,
      marginsType: 0,
      pageSize: 'A4',
      printSelectionOnly: false
    };
    
    // 현재 창의 webContents를 사용하여 PDF 생성
    console.log('📄 PDF 생성 중...');
    const pdfBuffer = await win.webContents.printToPDF(pdfOptions);
    
    // 파일 저장
    fs.writeFileSync(normalizedPath, pdfBuffer);
    console.log('✅ PDF 저장 완료:', normalizedPath);
    
    return { 
      success: true, 
      message: 'PDF가 저장되었습니다.',
      filePath: normalizedPath 
    };
    
  } catch (error) {
    console.error('❌ 정적 HTML PDF 내보내기 오류:', error);
    return { 
      success: false, 
      message: error.message || 'PDF 내보내기 중 오류가 발생했습니다.' 
    };
  }
});

/**
 * 정적 HTML 보고서에서 CSV 내보내기 핸들러
 * HTML에서 추출한 테이블 데이터를 CSV로 변환
 */
ipcMain.handle('export-csv-from-static', async (event, data) => {
  console.log('📊 정적 HTML에서 CSV 내보내기 요청 받음');
  
  try {
    const { rows, title } = data;
    
    if (!rows || !Array.isArray(rows) || rows.length === 0) {
      throw new Error('유효한 데이터가 없습니다.');
    }
    
    // 요청을 보낸 창 가져오기
    const win = BrowserWindow.fromWebContents(event.sender);
    if (!win) {
      throw new Error('창을 찾을 수 없습니다.');
    }
    
    // 저장 경로 선택 대화창
    const { filePath, canceled } = await dialog.showSaveDialog(win, {
      title: 'CSV 저장',
      defaultPath: `${title || '보고서'}_데이터_${new Date().toISOString().split('T')[0]}.csv`,
      filters: [
        { name: 'CSV 파일', extensions: ['csv'] }
      ]
    });
    
    if (canceled || !filePath) {
      console.log('📊 CSV 내보내기 취소됨');
      return { success: false, message: '취소되었습니다.' };
    }
    
    // 파일 경로 정규화
    const normalizedPath = path.normalize(filePath);
    console.log('📊 CSV 저장 경로:', normalizedPath);
    
    // CSV 문자열 변환 (RFC 4180 표준 준수)
    const csvContent = rows.map(row => {
      return row.map(cell => {
        const cellStr = String(cell || '');
        // 쉼표, 따옴표, 줄바꿈이 포함되면 따옴표로 감싸기
        if (cellStr.includes(',') || cellStr.includes('"') || cellStr.includes('\n')) {
          return `"${cellStr.replace(/"/g, '""')}"`;
        }
        return cellStr;
      }).join(',');
    }).join('\n');
    
    // BOM 추가 (Excel에서 한글 깨짐 방지)
    const bom = '\uFEFF';
    const csvWithBom = bom + csvContent;
    
    // 파일 저장
    fs.writeFileSync(normalizedPath, csvWithBom, 'utf8');
    console.log('✅ CSV 저장 완료:', normalizedPath);
    
    return { 
      success: true, 
      message: 'CSV가 저장되었습니다.',
      filePath: normalizedPath,
      rowCount: rows.length 
    };
    
  } catch (error) {
    console.error('❌ 정적 HTML CSV 내보내기 오류:', error);
    return { 
      success: false, 
      message: error.message || 'CSV 내보내기 중 오류가 발생했습니다.' 
    };
  }
});

console.log('✅ 내보내기 핸들러 등록 완료 (PDF, CSV, 정적 HTML)');

