import React from 'react';

const Header = ({ datasets, selectedId, onSelect }) => {
  return (
    <header className="header glass animate-fade-in">
      <div className="header-top">
        <div className="header-title">
          <h1>Dashboard</h1>
          <p>Public Opinion & PR Monitoring</p>
        </div>
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
