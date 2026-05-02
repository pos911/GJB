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
  const selectedDataset = datasets.find(d => d.id === selectedId);

  return (
    <header className="header glass animate-fade-in">
      <div className="header-top">
        <div className="header-title">
          <h1>서울국제정원박람회</h1>
          <p className="subtitle-long">네이버 뉴스·블로그·유튜브 데이터를 일자별로 수집해 서울국제정원박람회 관련 온라인 반응과 이슈를 모니터링합니다.</p>
          <p className="subtitle-short" style={{display: 'none'}}>일자별 온라인 반응·이슈 모니터링</p>
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

      {selectedDataset && (
        <div className="dataset-info">
          기준일 {selectedDataset.target_date} · 검색어 {selectedDataset.keyword} · 최종 생성 {formatKSTTime(selectedDataset.generated_at || lastScanTime)} KST
        </div>
      )}
    </header>
  );
};

export default Header;
