import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import SummaryCards from './components/SummaryCards';
import DataList from './components/DataList';
import './App.css';

function App() {
  const [datasets, setDatasets] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [summary, setSummary] = useState(null);
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(true);

  // Fetch available datasets
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

  // Fetch summary and details for selected dataset
  useEffect(() => {
    if (!selectedId) return;

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
          setLoading(false);
        })
        .catch(err => {
          console.error("Error loading data", err);
          setLoading(false);
        });
    }
  }, [selectedId, datasets]);

  return (
    <div className="app-container">
      <Header 
        datasets={datasets} 
        selectedId={selectedId} 
        onSelect={setSelectedId} 
      />
      
      {loading ? (
        <div className="loading">Loading data...</div>
      ) : datasets.length === 0 ? (
        <div className="empty-state">
          No data collected yet. Please run the Python collector script.
        </div>
      ) : (
        <>
          <SummaryCards summary={summary} />
          <DataList details={details} />
        </>
      )}
    </div>
  );
}

export default App;
