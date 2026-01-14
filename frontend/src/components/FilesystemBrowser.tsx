/**
 * FilesystemBrowser.tsx
 * File explorer component that browses actual filesystem structure
 * Supports: navigation, folder creation, sync with database
 */

import React, { useState } from 'react';
import {
  useFilesystemBrowser,
  useCreateFolder,
  useSyncFilesystem,
  useFolderTemplates,
  useApplyTemplate,
  getFileIcon,
  getFileColor,
  type FilesystemFolder,
  type FilesystemFile,
} from '../hooks/useFileManager';

interface FilesystemBrowserProps {
  clientId?: number;
  initialPath?: string;
  onFileSelect?: (file: FilesystemFile) => void;
  showSyncButton?: boolean;
  showTemplateButton?: boolean;
}

export function FilesystemBrowser({
  clientId,
  initialPath = 'clients',
  onFileSelect,
  showSyncButton = true,
  showTemplateButton = true,
}: FilesystemBrowserProps) {
  const [currentPath, setCurrentPath] = useState(initialPath);
  const [showNewFolderModal, setShowNewFolderModal] = useState(false);
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');

  // Queries
  const { data, isLoading, error, refetch } = useFilesystemBrowser({
    path: currentPath,
    client_id: clientId,
  });

  const { data: templates } = useFolderTemplates();

  // Mutations
  const createFolder = useCreateFolder();
  const syncFilesystem = useSyncFilesystem();
  const applyTemplate = useApplyTemplate();

  const handleFolderClick = (folder: FilesystemFolder) => {
    setCurrentPath(folder.path);
  };

  const handleBreadcrumbClick = (path: string) => {
    setCurrentPath(path);
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return;

    try {
      await createFolder.mutateAsync({
        path: currentPath,
        folder_name: newFolderName,
      });
      setNewFolderName('');
      setShowNewFolderModal(false);
      refetch();
    } catch (err) {
      console.error('Failed to create folder:', err);
    }
  };

  const handleSync = async () => {
    if (!clientId) return;

    try {
      const result = await syncFilesystem.mutateAsync({ client_id: clientId });
      alert(`Συγχρονίστηκαν ${result.synced} αρχεία`);
      refetch();
    } catch (err) {
      console.error('Sync failed:', err);
    }
  };

  const handleApplyTemplate = async (templateId: string) => {
    if (!clientId) return;

    try {
      const result = await applyTemplate.mutateAsync({
        client_id: clientId,
        template: templateId,
      });
      alert(result.message);
      setShowTemplateModal(false);
      refetch();
    } catch (err) {
      console.error('Template application failed:', err);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-2 text-gray-600">Φόρτωση...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
        <p className="text-red-600">Σφάλμα: {String(error)}</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow">
      {/* Header / Toolbar */}
      <div className="flex items-center justify-between p-4 border-b">
        {/* Breadcrumb */}
        <nav className="flex items-center space-x-2 text-sm">
          <button
            onClick={() => setCurrentPath('clients')}
            className="text-blue-600 hover:underline"
          >
            🏠 Root
          </button>
          {data?.breadcrumb?.map((item, index) => (
            <React.Fragment key={item.path}>
              <span className="text-gray-400">/</span>
              <button
                onClick={() => handleBreadcrumbClick(item.path)}
                className={`hover:underline ${
                  index === (data.breadcrumb?.length || 0) - 1
                    ? 'text-gray-900 font-medium'
                    : 'text-blue-600'
                }`}
              >
                {item.name}
              </button>
            </React.Fragment>
          ))}
        </nav>

        {/* Actions */}
        <div className="flex items-center space-x-2">
          <button
            onClick={() => refetch()}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded"
            title="Ανανέωση"
          >
            🔄
          </button>

          <button
            onClick={() => setShowNewFolderModal(true)}
            className="px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
          >
            📁 Νέος Φάκελος
          </button>

          {showTemplateButton && clientId && (
            <button
              onClick={() => setShowTemplateModal(true)}
              className="px-3 py-1.5 bg-purple-600 text-white rounded hover:bg-purple-700 text-sm"
            >
              📋 Template
            </button>
          )}

          {showSyncButton && clientId && (
            <button
              onClick={handleSync}
              disabled={syncFilesystem.isPending}
              className="px-3 py-1.5 bg-green-600 text-white rounded hover:bg-green-700 text-sm disabled:opacity-50"
            >
              {syncFilesystem.isPending ? '⏳ Sync...' : '🔄 Sync με DB'}
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        {!data?.exists ? (
          <div className="text-center py-8 text-gray-500">
            <p className="text-4xl mb-2">📁</p>
            <p>{data?.message || 'Ο φάκελος δεν υπάρχει'}</p>
            {clientId && (
              <button
                onClick={() => setShowTemplateModal(true)}
                className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                Δημιουργία Φακέλων
              </button>
            )}
          </div>
        ) : (
          <>
            {/* Stats */}
            <div className="mb-4 text-sm text-gray-500">
              {data.total_folders} φάκελοι, {data.total_files} αρχεία
            </div>

            {/* Folders */}
            {data.folders && data.folders.length > 0 && (
              <div className="mb-6">
                <h3 className="text-sm font-medium text-gray-700 mb-2">Φάκελοι</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2">
                  {data.folders.map((folder) => (
                    <button
                      key={folder.path}
                      onClick={() => handleFolderClick(folder)}
                      className="flex flex-col items-center p-3 rounded-lg hover:bg-blue-50 border border-transparent hover:border-blue-200 transition-colors"
                    >
                      <span className="text-3xl mb-1">📁</span>
                      <span className="text-sm text-gray-700 text-center truncate w-full">
                        {folder.name}
                      </span>
                      <span className="text-xs text-gray-400">
                        {folder.item_count} items
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Files */}
            {data.files && data.files.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-2">Αρχεία</h3>
                <div className="space-y-1">
                  {data.files.map((file) => (
                    <div
                      key={file.path}
                      onClick={() => onFileSelect?.(file)}
                      className={`flex items-center p-2 rounded hover:bg-gray-50 cursor-pointer ${
                        onFileSelect ? 'cursor-pointer' : ''
                      }`}
                    >
                      <span
                        className="text-xl mr-3"
                        style={{ color: getFileColor(file.extension.replace('.', '')) }}
                      >
                        📄
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-gray-900 truncate">{file.name}</p>
                        <p className="text-xs text-gray-500">
                          {file.size_display} • {new Date(file.modified).toLocaleDateString('el-GR')}
                        </p>
                      </div>
                      <div className="ml-2">
                        {file.in_database ? (
                          <span className="px-2 py-0.5 text-xs bg-green-100 text-green-700 rounded">
                            ✓ DB
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 text-xs bg-yellow-100 text-yellow-700 rounded">
                            Untracked
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Empty state */}
            {(!data.folders || data.folders.length === 0) &&
              (!data.files || data.files.length === 0) && (
                <div className="text-center py-8 text-gray-500">
                  <p className="text-4xl mb-2">📭</p>
                  <p>Ο φάκελος είναι άδειος</p>
                </div>
              )}
          </>
        )}
      </div>

      {/* New Folder Modal */}
      {showNewFolderModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-96">
            <h3 className="text-lg font-medium mb-4">Νέος Φάκελος</h3>
            <input
              type="text"
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              placeholder="Όνομα φακέλου"
              className="w-full px-3 py-2 border rounded-lg mb-4"
              autoFocus
            />
            <div className="flex justify-end space-x-2">
              <button
                onClick={() => {
                  setShowNewFolderModal(false);
                  setNewFolderName('');
                }}
                className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded"
              >
                Ακύρωση
              </button>
              <button
                onClick={handleCreateFolder}
                disabled={!newFolderName.trim() || createFolder.isPending}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              >
                {createFolder.isPending ? 'Δημιουργία...' : 'Δημιουργία'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Template Modal */}
      {showTemplateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-[500px] max-h-[80vh] overflow-y-auto">
            <h3 className="text-lg font-medium mb-4">Εφαρμογή Template Φακέλων</h3>
            <p className="text-sm text-gray-600 mb-4">
              Επιλέξτε ένα template για να δημιουργηθεί αυτόματα η δομή φακέλων:
            </p>
            <div className="space-y-2">
              {templates?.map((template) => (
                <button
                  key={template.id}
                  onClick={() => handleApplyTemplate(template.id)}
                  disabled={applyTemplate.isPending}
                  className="w-full p-4 text-left border rounded-lg hover:bg-blue-50 hover:border-blue-300 transition-colors"
                >
                  <div className="font-medium text-gray-900">{template.name}</div>
                  <div className="text-sm text-gray-600">{template.description}</div>
                  <div className="text-xs text-gray-400 mt-1">
                    {template.folder_count} φάκελοι
                  </div>
                </button>
              ))}
            </div>
            <div className="mt-4 flex justify-end">
              <button
                onClick={() => setShowTemplateModal(false)}
                className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded"
              >
                Κλείσιμο
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default FilesystemBrowser;
