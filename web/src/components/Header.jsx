import React from 'react';

function formatKSTTime(isoString) {
  if (!isoString) return '';
  try {
    const date = new Date(isoString);
    // KST = UTC+9
    const kstOptions = {
      timeZone: 'Asia/Seoul',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    };
    return date.toLocaleString('ko-KR', kstOptions);
  } catch {
    return isoString;
  }
}

const Header = ({ datasets, selectedId, onSelect, lastScanTime }) => {
  return (
    <header className="header glass animate-fade-in">
      <div className="header-top">
        <div className="header-title">
          <h1>Dashboard</h1>
          <p>Public Opinion &amp; PR Monitoring</p>
        </div>
        {lastScanTime && (
          <div className="last-scan">
            <span className="scan-dot"></span>
            <span className="scan-text">최종 스캔: {formatKSTTime(lastScanTime)}</span>
          </div>
        )}
      </div>
      
      <div className="header-controls">
        <select 
          className="select-dropdown" 
          value={selectedId || ''} 
          onChange={(e) => onSelect(e.target.value)}
        >
          {datasets.length === 0 && <option value="">No data available</option>}
          {datasets.map(d => (
            <option key={d.id} value={d.id}>
              {d.target_date} — {d.keyword}
            </option>
          ))}
        </select>
      </div>
    </header>
  );
};

export default Header;
