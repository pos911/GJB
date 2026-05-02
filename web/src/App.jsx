import { useState, useEffect, useMemo, useCallback } from 'react';
import Header from './components/Header';
import SummaryCards from './components/SummaryCards';
import FilterPanel from './components/FilterPanel';
import DataList from './components/DataList';
import AuditPanel from './components/AuditPanel';
import './App.css';

const STRONG_KEEP_TERMS = [
  '서울국제정원박람회',
  '2026 서울국제정원박람회',
  '서울 국제정원박람회',
  '서울숲 국제정원박람회'
];

function containsAny(text, terms) {
  if (!text || !terms || terms.length === 0) return false;
  const lower = text.toLowerCase();
  return terms.some(term => lower.includes(term.toLowerCase()));
}

function hasStrongKeepTerm(item) {
  const text = [
    item.title || '',
    item.description || '',
    item.author_or_channel || ''
  ].join(' ');
  return containsAny(text, STRONG_KEEP_TERMS);
}

function shouldShowItem(item, filterState) {
  const { activeCategory, toggles, excludeKeywords, strongKeywordPriority } = filterState;

  if (activeCategory !== 'all' && item.category !== activeCategory) {
    return false;
  }

  const text = [
    item.title || '',
    item.description || '',
    item.author_or_channel || ''
  ].join(' ');

  const hasStrong = strongKeywordPriority && hasStrongKeepTerm(item);

  if (toggles?.hide_pokemon) {
    const hasPokemon =
      (item.matched_issue_terms && item.matched_issue_terms.includes('포켓몬')) ||
      containsAny(text, ['포켓몬']);
    if (hasPokemon && !hasStrong) return false;
  }

  if (toggles?.hide_all_politicians) {
    const hasPolitician =
      (item.matched_political_terms && item.matched_political_terms.length > 0) ||
      (item.matched_politician_terms && Object.values(item.matched_politician_terms).some(v => v && v.length > 0));
    if (hasPolitician && !hasStrong) return false;
  }

  if (toggles?.hide_oh_sehoon) {
    const hasOh =
      (item.matched_politician_terms?.oh_sehoon && item.matched_politician_terms.oh_sehoon.length > 0) ||
      containsAny(text, ['오세훈']);
    if (hasOh && !hasStrong) return false;
  }

  if (toggles?.hide_jung_wonoh) {
    const hasJung =
      (item.matched_politician_terms?.jung_wonoh && item.matched_politician_terms.jung_wonoh.length > 0) ||
      containsAny(text, ['정원오']);
    if (hasJung && !hasStrong) return false;
  }

  if (toggles?.hide_district_mayor) {
    const hasMayor =
      (item.matched_politician_terms?.district_mayor && item.matched_politician_terms.district_mayor.length > 0) ||
      containsAny(text, ['구청장']);
    if (hasMayor && !hasStrong) return false;
  }

  if (toggles?.hide_political) {
    const isPolitical =
      item.category === 'political_context' ||
      (item.matched_political_terms && item.matched_political_terms.length > 0);
    if (isPolitical && !hasStrong) return false;
  }

  if (toggles?.hide_weak) {
    const isWeak = item.category === 'weak_match' || item.filter_status === 'review';
    if (isWeak && !hasStrong) return false;
  }

  if (excludeKeywords && excludeKeywords.trim()) {
    const keywords = excludeKeywords.split(',').map(k => k.trim()).filter(Boolean);
    if (keywords.length > 0 && containsAny(text, keywords) && !hasStrong) {
      return false;
    }
  }

  return true;
}

function App() {
  const [datasets, setDatasets] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [summary, setSummary] = useState(null);
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filterState, setFilterState] = useState({
    activeCategory: 'all',
    toggles: {},
    excludeKeywords: '',
    strongKeywordPriority: false
  });
  const [showAudit, setShowAudit] = useState(false);
  const [auditFileUrl, setAuditFileUrl] = useState('');
  const [lastScanTime, setLastScanTime] = useState('');

  useEffect(() => {
    fetch('/data/index.json')
      .then(res => {
        if (!res.ok) throw new Error('No data found');
        return res.json();
      })
      .then(data => {
        setDatasets(data);
        if (data.length > 0) {
          setSelectedId(data[0].id);
        } else {
          setLoading(false);
        }
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!selectedId) return;

    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    const dataset = datasets.find(d => d.id === selectedId);

    if (dataset) {
      Promise.all([
        fetch(dataset.summary_file).then(res => res.json()),
        fetch(dataset.details_file).then(res => res.json())
      ])
        .then(([summaryData, detailsData]) => {
          setSummary(summaryData);
          setDetails(detailsData);
          setAuditFileUrl(dataset.filter_audit_file || '');
          setLastScanTime(dataset.generated_at || '');
          setLoading(false);
        })
        .catch(err => {
          console.error('Error loading data', err);
          setLoading(false);
        });
    }
  }, [selectedId, datasets]);

  const filteredDetails = useMemo(() => {
    if (!details) return [];
    return details.filter(item => shouldShowItem(item, filterState));
  }, [details, filterState]);

  const categoryCounts = useMemo(() => {
    if (!details) return {};
    const counts = {};
    details.forEach(item => {
      const cat = item.category || 'unknown';
      counts[cat] = (counts[cat] || 0) + 1;
    });
    return counts;
  }, [details]);

  const visibleCountsBySource = useMemo(() => {
    const counts = {};
    filteredDetails.forEach(item => {
      counts[item.source] = (counts[item.source] || 0) + 1;
    });
    counts.total = filteredDetails.length;
    return counts;
  }, [filteredDetails]);

  const handleFilterChange = useCallback((state) => {
    setFilterState(state);
  }, []);

  return (
    <div className="app-container">
      <Header
        datasets={datasets}
        selectedId={selectedId}
        onSelect={setSelectedId}
        lastScanTime={lastScanTime}
      />

      {loading ? (
        <div className="loading">Loading data...</div>
      ) : datasets.length === 0 ? (
        <div className="empty-state">
          No data collected yet. Please run the Python collector script.
        </div>
      ) : (
        <>
          <SummaryCards summary={summary} visibleCountsBySource={visibleCountsBySource} />

          <FilterPanel
            onFilterChange={handleFilterChange}
            categoryCounts={categoryCounts}
            totalPublic={details ? details.length : 0}
            displayedCount={filteredDetails.length}
          />

          {auditFileUrl && (
            <button
              className="audit-toggle-btn glass"
              onClick={() => setShowAudit(true)}
            >
              제외 후보 보기
            </button>
          )}

          <DataList details={filteredDetails} />

          {showAudit && (
            <AuditPanel
              auditFileUrl={auditFileUrl}
              onClose={() => setShowAudit(false)}
            />
          )}
        </>
      )}
    </div>
  );
}

export default App;
