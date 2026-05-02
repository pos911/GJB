import { useState, useEffect } from 'react';
import './FilterPanel.css';

const CATEGORIES = [
  { id: 'all', label: '전체', icon: 'All', shortDesc: 'Public 노출 대상 전체 결과입니다.' },
  { id: 'confirmed', label: 'Only 국정박', icon: 'OK', shortDesc: '서울국제정원박람회 자체를 직접 다룬 결과입니다.' },
  { id: 'related_issue', label: '연계 이슈', icon: 'Issue', shortDesc: '포켓몬, 인파, 교통, 혼잡 등 행사와 연결된 이슈성 결과입니다.' },
  { id: 'comparison', label: '비교/연관', icon: 'Vs', shortDesc: '고양꽃박람회 등 타 행사와 함께 언급되거나 비교된 결과입니다.' },
  { id: 'political_context', label: '정치/인물', icon: 'Pol', shortDesc: '오세훈, 정원오, 구청장, 선거 등 정치·인물 맥락이 포함된 결과입니다.' },
  { id: 'weak_match', label: 'AI 검토대상', icon: 'Chk', shortDesc: '키워드는 잡혔지만 서울국제정원박람회 관련성이 불명확해 AI 검토가 필요한 결과입니다.' }
];

const QUICK_TOGGLES = [
  { id: 'hide_pokemon', label: '포켓몬 숨기기', icon: 'P' },
  { id: 'hide_all_politicians', label: '정치인 전체 숨기기', icon: 'All' },
  { id: 'hide_oh_sehoon', label: '오세훈 숨기기', icon: 'Oh' },
  { id: 'hide_jung_wonoh', label: '정원오 숨기기', icon: 'Jw' },
  { id: 'hide_district_mayor', label: '구청장 숨기기', icon: 'Gu' },
  { id: 'hide_political', label: '정치/인물 글 숨기기', icon: 'Pol' },
  { id: 'hide_weak', label: 'AI 검토대상 숨기기', icon: 'Chk' }
];

const STORAGE_KEY = 'gjb_filter_state';

function loadSavedState() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) return JSON.parse(saved);
  } catch {
    // Ignore invalid localStorage state.
  }
  return null;
}

function saveState(state) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Ignore localStorage write failures.
  }
}

const FilterPanel = ({ onFilterChange, categoryCounts, totalPublic, displayedCount }) => {
  const savedState = loadSavedState();

  const [activeCategory, setActiveCategory] = useState(savedState?.activeCategory || 'all');
  const [toggles, setToggles] = useState(savedState?.toggles || {});
  const [excludeKeywords, setExcludeKeywords] = useState(savedState?.excludeKeywords || '');
  const [strongKeywordPriority, setStrongKeywordPriority] = useState(
    savedState?.strongKeywordPriority !== undefined ? savedState.strongKeywordPriority : false
  );
  const [isExpanded, setIsExpanded] = useState(false);
  const [showDescriptions, setShowDescriptions] = useState(false);

  useEffect(() => {
    const state = { activeCategory, toggles, excludeKeywords, strongKeywordPriority };
    saveState(state);
    onFilterChange(state);
  }, [activeCategory, toggles, excludeKeywords, strongKeywordPriority, onFilterChange]);

  const handleToggle = (id) => {
    setToggles(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const hiddenCount = Math.max(totalPublic - displayedCount, 0);

  return (
    <div className="filter-panel glass animate-fade-in" style={{ animationDelay: '0.15s' }}>
      <div className="filter-stats-bar">
        <div className="filter-stat">
          <span className="filter-stat-label">전체 Public</span>
          <span className="filter-stat-value">{totalPublic}</span>
        </div>
        <div className="filter-stat">
          <span className="filter-stat-label">현재 표시</span>
          <span className="filter-stat-value accent">{displayedCount}</span>
        </div>
        {hiddenCount > 0 && (
          <div className="filter-stat">
            <span className="filter-stat-label">토글 숨김</span>
            <span className="filter-stat-value warning">{hiddenCount}</span>
          </div>
        )}
        {categoryCounts && Object.entries(categoryCounts).map(([cat, count]) => (
          count > 0 && (
            <div className="filter-stat" key={cat}>
              <span className="filter-stat-label">{CATEGORIES.find(c => c.id === cat)?.label || cat}</span>
              <span className="filter-stat-value">{count}</span>
            </div>
          )
        ))}
      </div>

      <div className="filter-section">
        <div className="filter-category-header">
          <button className="category-desc-toggle-btn" onClick={() => setShowDescriptions(!showDescriptions)}>
            카테고리 설명 {showDescriptions ? '▲' : '▼'}
          </button>
        </div>
        {showDescriptions && (
          <div className="category-desc-panel animate-fade-in">
            {CATEGORIES.filter(c => c.id !== 'all').map(cat => (
              <div key={cat.id} className="desc-item">
                <span className="desc-label cat-label-tag">{cat.label}</span>
                <span className="desc-text">{cat.shortDesc}</span>
              </div>
            ))}
            <div className="desc-item">
              <span className="desc-label cat-label-tag">제외 후보</span>
              <span className="desc-text">타 행사 단독, 무관, AI 무관 판정 결과로 기본 화면에는 노출하지 않고 검수 모드에서만 확인합니다.</span>
            </div>
          </div>
        )}
        <div className="filter-category-chips">
          {CATEGORIES.map(cat => (
            <button
              key={cat.id}
              className={`category-chip ${activeCategory === cat.id ? 'active' : ''} cat-${cat.id}`}
              onClick={() => setActiveCategory(cat.id)}
            >
              <span className="chip-icon">{cat.icon}</span>
              <span className="chip-label">{cat.label}</span>
              {cat.id !== 'all' && categoryCounts?.[cat.id] !== undefined && (
                <span className="chip-count">{categoryCounts[cat.id]}</span>
              )}
            </button>
          ))}
        </div>
      </div>

      <button
        className="filter-expand-btn"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        {isExpanded ? '상세 필터 접기' : '상세 필터 펼치기'}
      </button>

      {isExpanded && (
        <div className="filter-expanded">
          <div className="filter-section">
            <h4 className="filter-section-title">빠른 숨김</h4>
            <div className="toggle-grid">
              {QUICK_TOGGLES.map(toggle => (
                <label key={toggle.id} className="toggle-item">
                  <input
                    type="checkbox"
                    checked={!!toggles[toggle.id]}
                    onChange={() => handleToggle(toggle.id)}
                  />
                  <span className="toggle-slider"></span>
                  <span className="toggle-icon">{toggle.icon}</span>
                  <span className="toggle-label">{toggle.label}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="filter-section">
            <h4 className="filter-section-title">직접 제외 키워드</h4>
            <input
              type="text"
              className="keyword-input"
              placeholder="쉼표로 구분, 예: 포켓몬, 오세훈, 정원오"
              value={excludeKeywords}
              onChange={(e) => setExcludeKeywords(e.target.value)}
            />
          </div>

          <div className="filter-section">
            <label className="toggle-item priority-toggle">
              <input
                type="checkbox"
                checked={strongKeywordPriority}
                onChange={() => setStrongKeywordPriority(!strongKeywordPriority)}
              />
              <span className="toggle-slider"></span>
              <span className="toggle-label">본행사 핵심 키워드는 숨김 조건보다 우선 유지</span>
            </label>
            <p className="filter-hint">
              ON 시 서울국제정원박람회가 명확히 포함된 결과는 포켓몬/정치인 등 숨김 조건이 있어도 유지됩니다. 기본값은 OFF입니다.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default FilterPanel;
