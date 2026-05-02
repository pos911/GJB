const ICONS = {
  naver_news: 'News',
  naver_blog: 'Blog',
  youtube: 'YT',
  total: 'All'
};

const SummaryCards = ({ summary, visibleCountsBySource = {} }) => {
  if (!summary || summary.length === 0) return null;

  const totalStats = summary.find(stat => stat.source === 'total') || {};
  const hasFilterStats = totalStats.public_count !== undefined;

  return (
    <div className="summary-section animate-fade-in" style={{ animationDelay: '0.1s' }}>
      <div className="cards-grid">
        {summary.map((stat, index) => {
          const icon = ICONS[stat.source] || 'Src';
          const isError = stat.status === 'ERROR';
          const publicCount = stat.public_count ?? stat.current_run_deduped_count ?? 0;
          const visibleCount = visibleCountsBySource[stat.source] ?? publicCount;
          const excludedCount = stat.excluded_count ?? 0;

          return (
            <div key={stat.source} className="stat-card glass" style={{ animationDelay: `${0.1 + index * 0.1}s` }}>
              <div className="stat-card-header">
                <span className="stat-card-title">{stat.source_label}</span>
                <span className="stat-icon">{icon}</span>
              </div>
              <div className="stat-value">{publicCount}</div>
              <div className="stat-value-label">Public 노출</div>
              <div className="stat-sub stat-sub-stack">
                <span>현재 표시: {visibleCount}</span>
                <span>수집: {stat.raw_count ?? 0}</span>
                <span>Public: {publicCount}</span>
                <span>제외: {excludedCount}</span>
                <span className={!isError ? 'success' : 'error'}>
                  {isError ? 'Error' : 'Success'}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {hasFilterStats && (
        <div className="filter-stats-grid animate-fade-in" style={{ animationDelay: '0.25s' }}>
          <div className="filter-mini-card glass">
            <span className="mini-card-icon">All</span>
            <div className="mini-card-body">
              <span className="mini-card-value">{totalStats.total_collected_count || totalStats.collected_count || 0}</span>
              <span className="mini-card-label">전체 수집</span>
            </div>
          </div>
          <div className="filter-mini-card glass">
            <span className="mini-card-icon">Pub</span>
            <div className="mini-card-body">
              <span className="mini-card-value accent">{totalStats.public_count || 0}</span>
              <span className="mini-card-label">Public 노출</span>
            </div>
          </div>
          <div className="filter-mini-card glass">
            <span className="mini-card-icon">Hide</span>
            <div className="mini-card-body">
              <span className="mini-card-value warning">{totalStats.excluded_count || 0}</span>
              <span className="mini-card-label">Public 제외</span>
            </div>
          </div>
          {totalStats.existing_duplicate_skipped_count > 0 && (
            <div className="filter-mini-card glass">
              <span className="mini-card-icon">Dup</span>
              <div className="mini-card-body">
                <span className="mini-card-value">{totalStats.existing_duplicate_skipped_count}</span>
                <span className="mini-card-label">기존 중복</span>
              </div>
            </div>
          )}
          {totalStats.ai_used_count > 0 && (
            <div className="filter-mini-card glass">
              <span className="mini-card-icon">AI</span>
              <div className="mini-card-body">
                <span className="mini-card-value">{totalStats.ai_used_count}</span>
                <span className="mini-card-label">AI 판별</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SummaryCards;
